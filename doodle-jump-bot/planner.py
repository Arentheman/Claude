"""Логика бота: куда лететь, когда стрелять.

Все величины — в канонических пикселях (ширина игры 488) и секундах.
Ось Y направлена вниз (как на экране): vy > 0 — герой падает.
"""
import math
from dataclasses import dataclass

from vision import Scene


@dataclass
class Physics:
    gravity: float = 2100.0     # px/с²
    jump_speed: float = 785.0   # начальная скорость отскока, px/с (высота ≈ v²/2g ≈ 147 px)
    run_speed: float = 380.0    # горизонтальная скорость при зажатой A/D, px/с
    feet: float = 40.0          # от центра спрайта героя до «подошв»
    latency: float = 0.06       # задержка захват → нажатие, с


@dataclass
class Plan:
    move: str | None = None     # "left" / "right" / None
    fire: bool = False
    fire_at: tuple | None = None
    target: tuple | None = None  # куда хотим приземлиться (x, y) на экране
    note: str = ""


def wrap_dx(dx, W):
    """Кратчайшее смещение по X с учётом прохода сквозь края экрана."""
    dx = (dx + W / 2) % W - W / 2
    return dx


class Planner:
    def __init__(self, phys: Physics, cfg: dict | None = None):
        self.ph = phys
        cfg = cfg or {}
        self.deadband = cfg.get("deadband", 7.0)
        self.fire_cooldown = cfg.get("fire_cooldown", 0.25)
        self.fire_dx = cfg.get("fire_dx", 12.0)
        self.aim_fire = cfg.get("aim_fire", False)
        self.adapt = cfg.get("adapt_physics", True)
        self.apex_margin = cfg.get("apex_margin", 10.0)
        self.x_margin = cfg.get("x_margin", 6.0)
        self.hole_k = cfg.get("hole_radius_k", 0.25)   # радиус опасной зоны дыры = k * размер + 22
        self.reset()

    def reset(self):
        self.prev_t = None
        self.prev_wy = None
        self.prev_px = None
        self.world = 0.0          # накопленная прокрутка экрана
        self.vy = 0.0
        self.vx = 0.0
        self.last_fire = -1e9
        self.target_world = None  # (x, world_y) текущей цели — для «гистерезиса»
        self.bounce_wy = None
        self.apex_wy = None
        self.lost_frames = 0
        self.held = None
        self.held_since = 0.0
        self.bounces = []         # (t, x, мировая y) недавних отскоков
        self.cmds = []            # история команд (t, направление) за последние доли секунды

    # ------------------------------------------------------------------
    def _update_state(self, sc: Scene, t):
        p = sc.player
        self.world += sc.scroll
        if p is None:
            self.lost_frames += 1
            return False
        self.lost_frames = 0
        wy = p.y - self.world        # «мировая» высота героя (меньше = выше)
        if self.prev_t is not None and t > self.prev_t:
            dt = t - self.prev_t
            meas = (wy - self.prev_wy) / dt
            pred = self.vy + self.ph.gravity * dt     # модель: свободное падение
            if meas < pred - 350 and meas < -150:
                # Резкий рывок вверх = отскок (платформа, монстр, пружина).
                # Обычный отскок даёт известную скорость, пружина — больше.
                self.vy = min(-self.ph.jump_speed, meas)
                self.bounce_wy = self.prev_wy
                self.apex_wy = None
                self.bounces.append((t, p.x, self.prev_wy))
            else:
                self.vy = 0.7 * pred + 0.3 * meas
            dx = wrap_dx(p.x - self.prev_px, sc.width)
            self.vx = 0.5 * self.vx + 0.5 * dx / dt
            self._adapt(wy, t, abs(dx) / dt)
        self.prev_t, self.prev_wy, self.prev_px = t, wy, p.x
        return True

    def _adapt(self, wy, t, speed_now):
        """Подстройка физики под реальную игру по наблюдениям."""
        if not self.adapt:
            return
        # Высота прыжка: от точки отскока до вершины.
        if self.bounce_wy is not None and self.vy > 0 and self.apex_wy is None:
            self.apex_wy = wy
            rise = self.bounce_wy - wy
            if 60 < rise < 260:          # без пружин/ракет
                v = math.sqrt(2 * self.ph.gravity * rise)
                self.ph.jump_speed = 0.9 * self.ph.jump_speed + 0.1 * v
        # Скорость бега: когда клавиша зажата дольше 0.15 с.
        if self.held and t - self.held_since > 0.2 + self.ph.latency and 150 < speed_now < 900:
            self.ph.run_speed = 0.95 * self.ph.run_speed + 0.05 * speed_now

    # ------------------------------------------------------------------
    def _drift(self, t):
        """Куда ещё сдвинется герой из-за уже отданных, но не дошедших до игры команд.
        Считаем по истории команд — это точнее, чем измеренная скорость."""
        lat = self.ph.latency
        # Удаляем старые команды, но оставляем последнюю из них — она ещё действует.
        while len(self.cmds) > 1 and self.cmds[1][0] <= t - lat:
            self.cmds.pop(0)
        drift = 0.0
        for i, (tc, mv) in enumerate(self.cmds):
            t_end = self.cmds[i + 1][0] if i + 1 < len(self.cmds) else t
            a, b = max(tc, t - lat), t_end
            if b > a and mv:
                drift += (b - a) * self.ph.run_speed * (1 if mv == "right" else -1)
        return drift

    def _landing_time(self, dy, vy):
        """Через сколько секунд «подошвы» окажутся на dy ниже, двигаясь вниз."""
        g = self.ph.gravity
        disc = vy * vy + 2 * g * dy
        if disc < 0:
            return None
        return (-vy + math.sqrt(disc)) / g

    def _path_dangerous(self, sc: Scene, p, vy, dx, t_end):
        """Симулируем полёт к цели и проверяем дыры и монстров на пути."""
        ph = self.ph
        W = sc.width
        steps = max(2, int(t_end / 0.03))
        for i in range(steps + 1):
            t = t_end * i / steps
            move = max(0.0, t - ph.latency) * ph.run_speed
            x = p.x + math.copysign(min(abs(dx), move), dx)
            y = p.y + vy * t + 0.5 * ph.gravity * t * t
            for h in sc.holes:
                # Убивает только касание центра дыры — держим запас вокруг него.
                r = max(h.w, h.h) * self.hole_k + 22
                if wrap_dx(x - h.x, W) ** 2 + (y - h.y) ** 2 < r * r:
                    return True
            for m in sc.monsters:
                falling = vy + ph.gravity * t > 0
                # Прыжок сверху на монстра безопасен (он работает как платформа).
                if falling and y + ph.feet < m.y:
                    continue
                if abs(wrap_dx(x - m.x, W)) < m.w / 2 + 16 and abs(y - m.y) < m.h / 2 + 22:
                    return True
        return False

    def _choose_target(self, sc: Scene, p):
        ph = self.ph
        W = sc.width
        feet = p.y + ph.feet
        vy = self.vy
        best = None
        for q in sc.platforms:
            dy = q.y - feet
            if dy < -400:
                continue
            # Нужен запас по высоте: платформа, до которой еле дотягиваемся,
            # — частая причина промаха.
            if dy < 0 and vy < 0 and vy * vy / (2 * ph.gravity) < -dy + self.apex_margin:
                continue
            t = self._landing_time(dy, vy)
            if t is None or t < 0.04:
                continue
            xt = q.x + q.vx * t
            # Пока команда доходит до игры, герой летит с текущей скоростью.
            x0 = p.x + self.drift
            dx = wrap_dx(xt - x0, W)
            reach = ph.run_speed * max(0.0, t - ph.latency) + q.w / 2 + 4
            slack = reach - abs(dx)
            is_current = False
            if self.target_world is not None:
                tx, twy = self.target_world
                is_current = (abs(wrap_dx(q.x - tx, W)) < 30
                              and abs((q.y - self.world) - twy) < 20)
            # Новой цели нужен запас; уже выбранную держим, пока она достижима.
            if slack < (-2.0 if is_current else self.x_margin):
                continue
            if self._path_dangerous(sc, p, vy, dx, t):
                continue
            score = -q.y                                  # чем выше, тем лучше
            # После приземления герой снова взлетит вертикально вверх —
            # проверяем, что над точкой приземления нет дыры или монстра.
            lx = q.x + q.vx * t
            for h in sc.holes:
                if abs(wrap_dx(h.x - lx, W)) < max(h.w, h.h) * self.hole_k + 50 and q.y - 230 < h.y < q.y:
                    score -= 400
            for m in sc.monsters:
                if abs(wrap_dx(m.x - lx, W)) < m.w / 2 + 28 and q.y - 230 < m.y < q.y:
                    score -= 60 if self.aim_fire else 140
            score += 120 if q.bonus else 0
            score -= 50 if q.broken else 0
            score += min(slack, 50) * 0.6                 # запас по горизонтали
            if dy > 30:
                score -= 60                               # падать ниже — плохо
            if is_current:
                score += 35                               # держимся выбранной цели
            # Если долго прыгаем по одним и тем же платформам (сверху дыра или
            # нет пути) — штрафуем их, чтобы бот сместился и поискал другой путь.
            n = sum(1 for _, bx, by in self.bounces
                    if abs(wrap_dx(q.x - bx, W)) < 40 and abs((q.y - ph.feet - self.world) - by) < 40)
            if n >= 2:
                score -= 90 * (n - 1)
            if best is None or score > best[0]:
                best = (score, q, xt, dx, t, x0, reach)
        if best is None:
            return None
        # Садимся не в центр, а на тот край цели, что ближе к следующей ступеньке.
        score, q, xt, dx, t, x0, reach = best
        nxt = [q2 for q2 in sc.platforms if 20 < q.y - q2.y < 150 and not q2.broken]
        if nxt:
            q2 = min(nxt, key=lambda q2: abs(wrap_dx(q2.x - xt, W)))
            off = max(-q.w / 2 + 12, min(q.w / 2 - 12, wrap_dx(q2.x - xt, W)))
            dx2 = wrap_dx(xt + off - x0, W)
            if abs(dx2) <= reach - abs(off) - self.x_margin:
                xt, dx = xt + off, dx2
        return score, q, xt, dx, t

    # ------------------------------------------------------------------
    def step(self, sc: Scene, t) -> Plan:
        plan = Plan()
        if not self._update_state(sc, t):
            plan.note = "no player"
            return plan
        p = sc.player
        W = sc.width
        ph = self.ph

        # --- Стрельба: монстр над нами примерно в нашей колонке.
        for m in sc.monsters:
            ddx = wrap_dx(m.x - p.x, W)
            # Прицельный бросок (клик по монстру) — стреляем по любому монстру выше;
            # бросок пробелом летит вверх — только если монстр над головой.
            lim = W if self.aim_fire else m.w / 2 + self.fire_dx
            if m.y < p.y - 10 and abs(ddx) < lim and p.y - m.y < 700:
                if t - self.last_fire > self.fire_cooldown:
                    plan.fire = True
                    plan.fire_at = (m.x, m.y)
                    self.last_fire = t
                break

        self.drift = self._drift(t)
        self.bounces = [b for b in self.bounces if t - b[0] < 8.0]
        best = self._choose_target(sc, p)
        if best is not None:
            _, q, xt, dx, tl = best
            self.target_world = (q.x, q.y - self.world)
            plan.target = (xt % W, q.y)
            plan.note = f"target{' BONUS' if q.bonus else ''}{' broken' if q.broken else ''} t={tl:.2f}"
            if abs(dx) > self.deadband:
                plan.move = "right" if dx > 0 else "left"
        else:
            self.target_world = None
            plan.note = "no target"
            # Нет достижимой платформы: уходим от опасностей или к ближайшей платформе.
            danger = [h for h in sc.holes] + [m for m in sc.monsters]
            near = [d for d in danger if abs(wrap_dx(d.x - p.x, W)) < 90 and abs(d.y - p.y) < 250]
            if near:
                d = min(near, key=lambda d: abs(d.y - p.y))
                plan.move = "left" if wrap_dx(d.x - p.x, W) > 0 else "right"
                plan.note = "dodge"
            elif sc.platforms:
                below = [q for q in sc.platforms if q.y > p.y] or sc.platforms
                q = min(below, key=lambda q: abs(wrap_dx(q.x - p.x, W)) + 0.5 * abs(q.y - p.y))
                dx = wrap_dx(q.x - p.x, W)
                if abs(dx) > self.deadband:
                    plan.move = "right" if dx > 0 else "left"
                plan.target = (q.x, q.y)
        if plan.move != self.held:
            self.held = plan.move
            self.held_since = t
            self.cmds.append((t, plan.move))
        return plan
