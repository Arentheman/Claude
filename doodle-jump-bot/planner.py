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
        self.fire_dx = cfg.get("fire_dx", 4.0)
        self.aim_fire = cfg.get("aim_fire", False)
        self.adapt = cfg.get("adapt_physics", True)
        self.apex_margin = cfg.get("apex_margin", 10.0)
        self.x_margin = cfg.get("x_margin", 6.0)
        # Чёрная дыра (по записям): убивает касание центра, а в радиусе ~110 px
        # затягивает героя — тем сильнее, чем ближе (у центра ~400 px/с).
        self.safe_slack = cfg.get("safe_slack", 20.0)       # «надёжный» запас по дальности, px
        self.safe_vmargin = cfg.get("safe_vmargin", 20.0)   # и по высоте, px
        self.restart_after = cfg.get("stuck_restart_s", 25.0)  # 0 — не прыгать в бездну
        self.hole_kill_k = cfg.get("hole_kill_k", 0.25)   # смертельный радиус = k * размер + 20
        self.hole_margin = cfg.get("hole_margin", 10.0)   # запас к смертельному радиусу
        self.pull_r = cfg.get("hole_pull_radius", 110.0)
        self.pull_v = cfg.get("hole_pull_speed", 400.0)
        self.reset()

    def reset(self):
        self.prev_t = None
        self.prev_wy = None
        self.prev_px = None
        self.world = 0.0          # накопленная прокрутка экрана
        self.vy = 0.0
        self.vx = 0.0
        self.last_fire = -1e9
        self.bounce_wy = None
        self.apex_wy = None
        self.lost_frames = 0
        self.held = None
        self.held_since = 0.0
        self.bounces = []         # (t, x, мировая y) недавних отскоков
        self.hunting = False
        self.drift = 0.0
        self.cmds = []            # история команд (t, направление) за последние доли секунды
        self.jump_id = 0          # номер прыжка (растёт на каждом отскоке)
        self.lock = None          # цель, выбранная в этом прыжке: (x, мировая y, jump_id)
        self.best_wy = None       # лучшая высота за игру (мировая y, меньше = выше)
        self.progress_t = None    # когда последний раз поднялись выше
        self.restarting = False
        self._last_override = None

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
                # Точка отскока — верх платформы под ногами (если нашли её);
                # по позиции из прошлого кадра высота прыжка занижается.
                self.bounce_wy = None
                for q in sc.platforms:
                    if abs(wrap_dx(q.x - p.x, sc.width)) < q.w / 2 + 12 and -45 < q.y - (p.y + self.ph.feet) < 45:
                        self.bounce_wy = q.y - self.ph.feet - self.world
                        break
                self.apex_wy = None
                self.bounces.append((t, p.x, self.prev_wy))
                self.jump_id += 1
            else:
                self.vy = 0.7 * pred + 0.3 * meas
            dx = wrap_dx(p.x - self.prev_px, sc.width)
            self.vx = 0.5 * self.vx + 0.5 * dx / dt
            self._adapt(wy, t, abs(dx) / dt)
        if self.best_wy is None or wy < self.best_wy - 25:
            self.best_wy = wy
            self.progress_t = t
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

    def _kill_r(self, h):
        return max(h.w, h.h) * self.hole_kill_k + 20 + self.hole_margin

    def _pull(self, sc: Scene, x, y):
        """Скорость, с которой дыры тянут героя в точке (x, y)."""
        W = sc.width
        vx = vy = 0.0
        for h in sc.holes:
            hx, hy = wrap_dx(h.x - x, W), h.y - y
            d = math.hypot(hx, hy)
            if 1.0 < d < self.pull_r:
                v = self.pull_v * (1.0 - d / self.pull_r)
                vx += v * hx / d
                vy += v * hy / d
        return vx, vy

    def _hole_gap(self, sc: Scene, x, y):
        """Расстояние до смертельной зоны ближайшей дыры (< 0 — смерть)."""
        W = sc.width
        return min((math.hypot(wrap_dx(x - h.x, W), y - h.y) - self._kill_r(h) for h in sc.holes),
                   default=1e9)

    def _rise_safe(self, sc: Scene, lx, ly):
        """Взлёт после отскока в точке (lx, ly): можно ли пролететь мимо дыр,
        уходя от них вбок? Учитываем затягивание."""
        if not sc.holes:
            return True
        ph = self.ph
        W = sc.width
        x, y, vy = lx, ly, -ph.jump_speed
        t, dt = 0.0, 0.02
        while vy < 0 and t < 1.0:
            h = min(sc.holes, key=lambda h: math.hypot(wrap_dx(x - h.x, W), y - h.y))
            away = 1.0 if wrap_dx(x - h.x, W) >= 0 else -1.0
            px, py = self._pull(sc, x, y)
            steer = away * ph.run_speed if t >= ph.latency else 0.0
            x = (x + (steer + px) * dt) % W
            vy += ph.gravity * dt
            y += (vy + py) * dt
            if self._hole_gap(sc, x, y) < 0:
                return False
            t += dt
        return True

    def _path_dangerous(self, sc: Scene, p, vy, dx, t_end):
        """Симулируем полёт к цели и проверяем дыры и монстров на пути."""
        ph = self.ph
        W = sc.width
        x, y, v = p.x + 0.0, p.y + 0.0, vy
        moved, t, dt = 0.0, 0.0, 0.02
        steer = math.copysign(ph.run_speed, dx)
        while t <= t_end:
            if t >= ph.latency and moved < abs(dx):
                x += steer * dt
                moved += ph.run_speed * dt
            px, py = self._pull(sc, x, y)
            x += px * dt
            v += ph.gravity * dt
            y += (v + py) * dt
            t += dt
            if sc.holes and self._hole_gap(sc, x, y) < 0:
                return True
            for m in sc.monsters:
                if self._will_shoot(m, p):
                    continue
                falling = v > 0
                # Прыжок сверху на монстра безопасен (он работает как платформа).
                if falling and y + ph.feet < m.y:
                    continue
                if abs(wrap_dx(x - m.x, W)) < m.w / 2 + 16 and abs(y - m.y) < m.h / 2 + 22:
                    return True
        return False

    def _clearance(self, sc: Scene, p, move, horizon=0.75, travel=None):
        """Короткая симуляция (с отскоками от платформ) при заданной команде.
        Возвращает минимальный запас до опасности: < 0 — столкновение."""
        ph = self.ph
        W = sc.width
        x, y, vy = p.x + self.drift, p.y, self.vy
        dirv = {"left": -1, "right": 1}.get(move, 0)
        dt = 0.02
        best = 1e9
        t = 0.0
        moved = 0.0
        while t < horizon:
            if t >= ph.latency and (travel is None or moved < travel):
                x = (x + dirv * ph.run_speed * dt) % W
                moved += ph.run_speed * dt
            px, py = self._pull(sc, x, y)
            x = (x + px * dt) % W
            oy = y
            vy += ph.gravity * dt
            y += (vy + py) * dt
            if vy > 0:
                for q in sc.platforms:
                    if oy + ph.feet <= q.y <= y + ph.feet and abs(wrap_dx(x - q.x, W)) < q.w / 2 + 10:
                        vy, y = -ph.jump_speed, q.y - ph.feet
                        break
            if sc.holes:
                best = min(best, self._hole_gap(sc, x, y))
            for m in sc.monsters:
                if vy > 0 and y + ph.feet < m.y:
                    continue                      # прыжок сверху — безопасно
                if self._will_shoot(m, p):
                    continue
                d = max(abs(wrap_dx(x - m.x, W)) - (m.w / 2 + 16), abs(y - m.y) - (m.h / 2 + 22))
                best = min(best, d)
            t += dt
        return best

    def _safe_move(self, sc: Scene, p, move, travel=None):
        """Если запланированное движение ведёт в монстра/дыру — берём безопасное.
        travel — сколько px бот собирается пройти (дальше он остановится)."""
        if not sc.holes and not sc.monsters:
            return move, False
        options = [move] + [m for m in (None, "left", "right") if m != move]
        scores = [(self._clearance(sc, p, m, travel=travel if m == move else None), m) for m in options]
        # Гистерезис: если в прошлом кадре уже уводили от опасности, возвращаемся
        # к плану только при уверенном запасе — иначе бот дёргается туда-сюда.
        need = 14 if self._last_override is not None else 4
        if scores[0][0] > need:
            self._last_override = None
            return move, False
        prev = [c for c in scores if self._last_override is not None
                and c[1] == self._last_override[0] and c[0] > 4]
        safest = prev[0] if prev else max(scores, key=lambda c: c[0])
        # Храним кортеж: «стоять» (None) — тоже вариант увода от опасности.
        self._last_override = (safest[1],) if safest[1] != move else None
        return safest[1], safest[1] != move

    def _will_shoot(self, m, p):
        """Режим «охоты» (застряли): монстра, висящего над нами, мы собьём
        выстрелом раньше, чем долетим, поэтому не считаем его препятствием."""
        return self.hunting and m.y < p.y - 90

    def _dx_keep_dir(self, dx, W):
        """Цель почти напротив (через край экрана примерно так же далеко) —
        не меняем направление туда-сюда, продолжаем в ту же сторону."""
        if self.held and abs(dx) > W / 2 - 60:
            alt = dx - math.copysign(W, dx)
            # Только если оба пути почти равны — иначе лишний крюк через край
            # делает близкую платформу «недостижимой».
            if (alt > 0) == (self.held == "right") and abs(alt) - abs(dx) < 30:
                return alt
        return dx

    def _stuck_level(self, p, W):
        if not self.bounces:
            return 0
        _, bx, by = self.bounces[-1]
        return sum(1 for _, x, y in self.bounces
                   if abs(wrap_dx(x - bx, W)) < 60 and abs(y - by) < 40)

    def _choose_target(self, sc: Scene, p):
        """Куда лететь. Принцип: надёжно важнее высоко. Платформа с запасом по
        высоте и дальности лучше далёкой «на пределе», даже если до неё
        понадобится лишний прыжок. Выбранная цель держится весь прыжок."""
        ph = self.ph
        W = sc.width
        feet = p.y + ph.feet
        vy = self.vy
        apex = vy * vy / (2 * ph.gravity) if vy < 0 else 0.0
        stuck = self._stuck_level(p, W)
        locked = self.lock is not None and self.lock[2] == self.jump_id
        lb = self.bounces[-1] if self.bounces else None
        # Уровень отсчёта подъёма — «ноги» в момент последнего отскока.
        base_wy = (lb[2] + ph.feet) if lb is not None else (feet - self.world)
        best, best_key = None, None
        for q in sc.platforms:
            dy = q.y - feet
            if dy < -400:
                continue
            # Запас по высоте: насколько вершина прыжка выше платформы.
            vmargin = apex + dy if dy < 0 else 999.0
            if dy < 0 and (vy >= 0 or vmargin < self.apex_margin):
                continue
            t = self._landing_time(dy, vy)
            if t is None or t < 0.04:
                continue
            xt = q.x + q.vx * t
            # Пока команда доходит до игры, герой летит с текущей скоростью.
            x0 = p.x + self.drift
            dx = self._dx_keep_dir(wrap_dx(xt - x0, W), W)
            reach = ph.run_speed * max(0.0, t - ph.latency) + q.w / 2 + 4
            slack = reach - abs(dx)
            is_current = (locked and abs(wrap_dx(q.x - self.lock[0], W)) < 30
                          and abs((q.y - self.world) - self.lock[1]) < 20)
            # Выбранную в этом прыжке цель держим, пока до неё можно долететь;
            # новой цели нужен нормальный запас.
            if slack < (-2.0 if is_current else self.x_margin):
                continue
            if self._path_dangerous(sc, p, vy, dx, t):
                continue
            lx = xt
            away = None
            ly = q.y - ph.feet
            near = [h for h in sc.holes if abs(wrap_dx(lx - h.x, W)) < self.pull_r + q.w / 2
                    and ly - 260 - self.pull_r < h.y < ly + self.pull_r]
            hole_risk = 0.0
            if near:
                h = min(near, key=lambda h: abs(wrap_dx(lx - h.x, W)))
                side = 1 if wrap_dx(lx - h.x, W) >= 0 else -1
                if not self._rise_safe(sc, lx + side * (q.w / 2 - 6), ly):
                    continue                             # с этой платформы затянет в дыру
                if not self._rise_safe(sc, lx, ly):
                    away = side                          # садиться только на дальний край
                hole_risk = 60.0

            comfortable = slack >= self.safe_slack and vmargin >= self.safe_vmargin and not hole_risk
            # Подъём считаем от платформы, с которой оттолкнулись (а не от текущей
            # точки полёта): иначе «остаться» кажется хуже рискованного прыжка.
            qwy = q.y - self.world
            gain = max(-250.0, min(170.0, base_wy - qwy))
            own = (lb is not None and abs(wrap_dx(q.x - lb[1], W)) < q.w / 2 + 12
                   and abs(qwy - ph.feet - lb[2]) < 30)
            if own and stuck >= 4:
                continue                                  # прыгаем на месте — пора уходить
            score = 2.0 * gain + 0.8 * min(slack, 50.0) + 0.5 * min(vmargin, 40.0)
            score -= hole_risk
            for m in sc.monsters:
                if abs(wrap_dx(m.x - lx, W)) < m.w / 2 + 28 and q.y - 230 < m.y < q.y:
                    score -= 0 if self.hunting else (100 if self.aim_fire else 300)
            if q.bonus and comfortable:
                score += 80
            score -= 50 if q.broken else 0
            if q.y > sc.height - 70:
                score -= 150                              # у нижнего края — легко упасть
            if stuck >= 4 and q.y < sc.height * 0.75:
                score += 0.6 * min(abs(wrap_dx(q.x - lb[1], W)), 150)   # уходим вбок
            if is_current:
                score += 500                              # не дёргаемся между целями
            # Два уровня: надёжные цели всегда важнее рискованных.
            tier = 1 if (comfortable or is_current) else 0
            key = (tier, score)
            if best is None or key > best_key:
                best, best_key = (score, q, xt, dx, t, x0, reach, away), key
        if best is None:
            return None
        score, q, xt, dx, t, x0, reach, away = best
        self.lock = (q.x, q.y - self.world, self.jump_id)
        if away is not None:
            off = away * (q.w / 2 - 6)
            dx2 = self._dx_keep_dir(wrap_dx(xt + off - x0, W), W)
            if abs(dx2) <= reach - abs(off) - self.x_margin:
                return score, q, xt + off, dx2, t
        # Садимся не в центр, а на тот край цели, что ближе к следующей ступеньке:
        # с края следующий прыжок короче и надёжнее. При охоте — точно под монстра.
        prey = [m for m in sc.monsters if q.y - 260 < m.y < q.y
                and abs(wrap_dx(m.x - xt, W)) < q.w / 2 + m.w / 2] if self.hunting else []
        nxt = [q2 for q2 in sc.platforms if 20 < q.y - q2.y < 160 and not q2.broken]
        aim = None
        if prey:
            aim = prey[0].x
        elif nxt:
            aim = min(nxt, key=lambda q2: abs(wrap_dx(q2.x - xt, W))).x
        if aim is not None:
            off = max(-q.w / 2 + 6, min(q.w / 2 - 6, wrap_dx(aim - xt, W)))
            dx2 = self._dx_keep_dir(wrap_dx(xt + off - x0, W), W)
            if abs(dx2) <= reach - abs(off) - self.x_margin:
                xt, dx = xt + off, dx2
        return score, q, xt, dx, t

    def _steer(self, dx):
        """Руление с гистерезисом: уже едем к цели — едем до самого конца;
        начинаем движение или разворачиваемся только при заметном промахе."""
        want = "right" if dx > 0 else "left"
        if abs(dx) <= 3:
            return None
        if self.held == want:
            return want
        if abs(dx) > self.deadband + (6 if self.held else 0):
            return want
        return None

    def _restart_move(self, sc: Scene, p):
        """Нет прогресса слишком долго — уходим туда, где под героем нет
        платформ, чтобы упасть и начать игру заново."""
        W = sc.width
        below = [(q.x, q.w) for q in sc.platforms if q.y > p.y - 20]
        below += [(m.x, m.w) for m in sc.monsters if m.y > p.y - 20]
        best_x, best_cost = p.x, 1e9
        for x in range(12, W, 12):
            cost = sum(max(0.0, 1.0 - abs(wrap_dx(bx - x, W)) / (bw / 2 + 30)) for bx, bw in below)
            cost += 0.3 * abs(wrap_dx(x - p.x, W)) / W
            if cost < best_cost:
                best_x, best_cost = x, cost
        dx = wrap_dx(best_x - (p.x + self.drift), W)
        if abs(dx) <= self.deadband:
            return None, best_x
        return ("right" if dx > 0 else "left"), best_x

    # ------------------------------------------------------------------
    def step(self, sc: Scene, t) -> Plan:
        plan = Plan()
        if not self._update_state(sc, t):
            plan.note = "no player"
            # Герой пропал на пару кадров (например, наполовину ушёл за край
            # экрана) — продолжаем начатое движение, а не бросаем управление.
            if self.lost_frames <= 6:
                plan.move = self.held
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
        self.hunting = self._stuck_level(p, W) >= 3 and any(m.y < p.y for m in sc.monsters)
        self.bounces = [b for b in self.bounces if t - b[0] < 8.0]

        # Долго нет новой высоты (вечный цикл на одних платформах) — прыгаем
        # в бездну: игра перезапустится сама.
        if self.restart_after and self.progress_t is not None and t - self.progress_t > self.restart_after:
            if not self.restarting:
                self.restarting = True
            plan.move, tx = self._restart_move(sc, p)
            plan.target = (tx, p.y + 200)
            plan.note = f"restart: no progress {t - self.progress_t:.0f}s"
            plan.fire = False
            if plan.move != self.held:
                self.held = plan.move
                self.held_since = t
                self.cmds.append((t, plan.move))
            return plan

        best = self._choose_target(sc, p)
        self._plan_dx = None
        if best is not None:
            _, q, xt, dx, tl = best
            self._plan_dx = dx
            plan.target = (xt % W, q.y)
            plan.note = f"target{' BONUS' if q.bonus else ''}{' broken' if q.broken else ''} t={tl:.2f}"
            plan.move = self._steer(dx)
        else:
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
        travel = abs(self._plan_dx) if self._plan_dx is not None else None
        plan.move, overridden = self._safe_move(sc, p, plan.move, travel)
        if overridden:
            plan.note += " SAFE"
        if plan.move != self.held:
            self.held = plan.move
            self.held_since = t
            self.cmds.append((t, plan.move))
        return plan
