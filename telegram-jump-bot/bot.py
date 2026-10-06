"""
Нейро-бот для Doodle-Jump-подобной игры в Telegram mini-app.

Бот смотрит на экран, находит персонажа, платформы и врагов, и нейросеть решает,
что нажать: A / D (влево / вправо) и клик левой кнопкой по врагу.
Сеть учится сама — нейроэволюцией: каждая попытка оценивается по высоте и убитым
врагам, лучшие сети размножаются с мутациями.

Команды:
    python bot.py setup              настроить область игры и кнопку «играть снова»
    python bot.py debug              показать, что бот видит (ничего не нажимает)
    python bot.py debug --image x.png  проверить распознавание на скриншоте
    python bot.py train              учиться (прогресс сохраняется в population.json)
    python bot.py play               играть лучшей найденной сетью

Горячие клавиши во время работы: F9 — пауза / продолжить, F10 — выход.
"""
import argparse
import json
import os
import random
import sys
import math
import time

import cv2
import numpy as np

if getattr(sys, "frozen", False):
    # Собранный .exe: свои файлы кладём рядом с ним, а предобученные сети лежат внутри
    HERE = os.path.dirname(sys.executable)
    BUNDLE = getattr(sys, "_MEIPASS", HERE)
else:
    HERE = BUNDLE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")
STATE_PATH = os.path.join(HERE, "population.json")
PRETRAINED_PATH = os.path.join(BUNDLE, "pretrained.json")
DEBUG_WINDOW = "Что видит бот"


def set_dpi_aware():
    # Без этого на Windows с масштабом 125–150% координаты скриншота и мыши не совпадут
    if sys.platform == "win32":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass


# ============================================================================
# Нейросеть: 26 входов -> 12 tanh -> 2 выхода (руль, бросок).
# Раскладка весов совпадает с pretrain/sim.js, поэтому предобученные сети подходят.
# ============================================================================
NI, NH, NO = 26, 12, 2
O_B1 = NI * NH
O_W2 = O_B1 + NH
O_B2 = O_W2 + NH * NO
NG = O_B2 + NO
# Входы, которые меняют знак при зеркальном отражении сцены (все «смещения по X»)
MIRROR = [0, 2, 4, 6, 8, 10, 12, 14, 17, 18, 21]
DEADZONE = 0.05


def think(g, inp):
    w1 = g[:O_B1].reshape(NH, NI)
    w2 = g[O_W2:O_B2].reshape(NO, NH)
    hid = np.tanh(w1 @ inp + g[O_B1:O_W2])
    return np.tanh(w2 @ hid + g[O_B2:])


def decide(g, inp):
    """Сеть смотрит на сцену и на её зеркало; руль — разница ответов,
    поэтому он симметричен и сети остаётся выучить только «куда лучше»."""
    mir = inp.copy()
    mir[MIRROR] *= -1
    o, om = think(g, inp), think(g, mir)
    steer = o[0] - om[0]
    move = -1 if steer < -DEADZONE else 1 if steer > DEADZONE else 0
    return move, (o[1] + om[1]) > 0, steer


# ============================================================================
# Распознавание
# ============================================================================
OBJ_DARK = 100


class Detector:
    """Ищет на кадре платформы, персонажа и врагов.

    1. Всё, что заметно темнее медианы своей строки, — объект (фон — плавный градиент).
    2. Платформы — длинные горизонтальные полосы: их выделяем первыми и вырезаем,
       чтобы персонаж, стоящий на платформе, не слипался с ней.
    3. Оставшиеся пятна сортируем по цвету (пороги подобраны по записям игры):
       персонаж — немного розово-бежевого (кожа) и зелёная шапка; свинья — почти вся розовая;
       чёрная дыра — фиолетовая; призрак — голубой; пружины и бонусы без розового пропускаем.
    """

    def __init__(self, scale=0.5, top_ignore=0.09):
        self.scale = scale
        self.top_ignore = top_ignore  # верхняя полоса со счётом и значками
        self.prev_player = None

    def detect(self, bgr):
        H, W = bgr.shape[:2]
        s = self.scale
        small8 = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        small = small8.astype(np.int16)
        bg = np.median(small, axis=1, keepdims=True)
        diff = np.abs(small - bg).sum(axis=2)
        darker = bg.sum(axis=2) - small.sum(axis=2)
        # Ночью фон тёмный и объекты могут быть светлее его — там важна сама разница с фоном
        night = bg.sum(axis=2)[:, 0] < 330
        if night.any():
            darker[night] = np.maximum(darker[night], diff[night])
        mask = ((diff > 60) & (darker > 30)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        hsv = cv2.cvtColor(small8, cv2.COLOR_BGR2HSV)
        top = int(self.top_ignore * H * s)

        # Для платформ и объектов порог строже: контуры облаков светлее, и с ними
        # платформы и персонаж слипались в одно пятно
        strong = cv2.morphologyEx(((diff > 60) & (darker > OBJ_DARK)).astype(np.uint8), cv2.MORPH_CLOSE,
                                  np.ones((3, 3), np.uint8))
        # --- платформы: горизонтальные полосы шире персонажа
        kw = max(3, int(0.055 * W * s))
        runs = cv2.morphologyEx(strong, cv2.MORPH_OPEN, np.ones((1, kw), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(runs)
        plats = []
        plat_mask = np.zeros_like(mask)
        for i in range(1, n):
            x, y, w, h, a = st[i]
            fw, fh = w / s, h / s
            # платформы ~62 px при ширине игры 480 (0.13 W), персонаж ~46 px — он уже
            if y < top or not (0.11 * W <= fw <= 0.25 * W and fh <= 0.045 * W):
                continue
            comp = lab[y:y + h, x:x + w] == i
            if darker[y:y + h, x:x + w][comp].mean() < 150:  # контуры облаков
                continue
            hue = hsv[y:y + h, x:x + w, 0][comp]
            brown = float(np.mean((hue >= 5) & (hue <= 22)))
            plats.append({"x": (x + w / 2) / s, "y": y / s, "w": fw, "type": "b" if brown > 0.5 else "n"})
            plat_mask[y:y + h, x:x + w][comp] = 1
        plats = merge_overlapping(plats)
        obj = strong & (1 - cv2.dilate(plat_mask, np.ones((3, 3), np.uint8)))

        # --- остальные объекты
        n, lab, st, _ = cv2.connectedComponentsWithStats(obj)
        blobs = []
        for i in range(1, n):
            x, y, w, h, a = st[i]
            fw, fh = w / s, h / s
            cy = (y + h / 2) / s
            # внизу слева бывает значок поверх игры — нижние 3% экрана не смотрим
            if cy < self.top_ignore * H or cy > 0.97 * H or not (0.045 * W <= fw <= 0.3 * W and 0.045 * W <= fh <= 0.3 * W):
                continue
            if a / float(w * h) < 0.3:
                continue
            comp = lab[y:y + h, x:x + w] == i
            px = hsv[y:y + h, x:x + w][comp].astype(np.int16)
            if darker[y:y + h, x:x + w][comp].mean() < 150:
                continue
            hh, ss, vv = px[:, 0], px[:, 1], px[:, 2]
            f = {
                "pink": float(np.mean(((hh <= 10) | (hh >= 165)) & (ss > 60))),
                "purple": float(np.mean((hh >= 120) & (hh < 165) & (ss > 60))),
                "blue": float(np.mean((hh >= 85) & (hh < 120) & (ss > 40))),
                "skin": float(np.mean((hh >= 5) & (hh <= 25) & (ss > 40) & (vv > 90))),
                "green": float(np.mean((hh >= 35) & (hh <= 85) & (ss > 60))),
            }
            if f["green"] > 0.1 and fw / fh < 0.65:
                kind = "item"  # ракета: узкая, с зелёным носом (у персонажа зелёного ~0.04)
            elif f["purple"] > 0.4:
                kind = "hole"
            elif f["blue"] > 0.5:
                kind = "ghost"
            elif f["pink"] > 0.45:
                kind = "pig"
            elif 0.09 <= f["pink"] <= 0.42 and 0.12 < f["skin"] < 0.7:
                kind = "player?"  # у персонажа «кожи» ~30%; сплошь оранжевое — искры ломающейся платформы
            elif f["pink"] < 0.09 or f["skin"] >= 0.7:
                kind = "item"  # пружины, ракеты, бонусы и оранжевые искры ломающейся платформы
            else:
                kind = "enemy"
            blobs.append({"x": (x + w / 2) / s, "y": cy, "w": fw, "h": fh, "kind": kind, **f})

        for g in self._ghosts(bgr, W, H):
            blobs = [b for b in blobs if abs(b["x"] - g["x"]) + abs(b["y"] - g["y"]) > 0.08 * W]
            blobs.append(g)

        player = self._pick_player([b for b in blobs if b["kind"] == "player?"], W, H)
        # Лишние «кандидаты в персонажа» врагами не считаем: это бывают искры от ломающейся
        # платформы или пружина, и сеть начинала шарахаться от таких платформ
        enemies = [b for b in blobs if b is not player and b["kind"] in ("pig", "ghost", "hole", "enemy")]
        if player is not None:
            self.prev_player = (player["x"], player["y"])
        # Пружина стоит на платформе: прыжок с такой платформы уносит очень высоко
        for b in blobs:
            if b is player or b["kind"] not in ("item", "player?"):
                continue
            bottom = b["y"] + b["h"] / 2
            for pl in plats:
                if abs(wdx(pl["x"], b["x"], W)) < pl["w"] / 2 and -0.02 * H < bottom - pl["y"] < 0.02 * H and b["h"] < 0.07 * H:
                    pl["spring"] = (b["x"], b["w"])
        return {"W": W, "H": H, "plats": plats, "player": player, "enemies": enemies,
                "items": [b for b in blobs if b is not player and b["kind"] in ("item", "player?")]}

    _ghost_tpl = None

    def _ghosts(self, bgr, W, H):
        """Призраки светло-голубые и почти не отличаются от неба по цвету, поэтому ищем их
        по форме — образцу из записи игры (sprites/ghost.png). Совпадение у настоящих
        призраков 0.74–0.98, у всего остального не выше 0.45."""
        if Detector._ghost_tpl is None:
            tpl = cv2.imread(os.path.join(BUNDLE, "sprites", "ghost.png"))
            msk = cv2.imread(os.path.join(BUNDLE, "sprites", "ghost_mask.png"), 0)
            Detector._ghost_tpl = (tpl, msk) if tpl is not None and msk is not None else False
        if not Detector._ghost_tpl:
            return []
        tpl, msk = Detector._ghost_tpl
        k = 0.25 * W / 480.0  # образец снят при ширине игры 480
        t = cv2.resize(tpl, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
        m = cv2.resize(msk, (t.shape[1], t.shape[0]), interpolation=cv2.INTER_NEAREST)
        sm = cv2.resize(bgr, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
        if sm.shape[0] < t.shape[0] or sm.shape[1] < t.shape[1]:
            return []
        r = np.nan_to_num(cv2.matchTemplate(sm, t, cv2.TM_CCOEFF_NORMED, mask=m), nan=0, posinf=0, neginf=0)
        out = []
        for _ in range(3):
            _, mx, _, (lx, ly) = cv2.minMaxLoc(r)
            if mx < 0.6:
                break
            cx, cy = (lx + t.shape[1] / 2) / 0.25, (ly + t.shape[0] / 2) / 0.25
            if cy > self.top_ignore * H:
                out.append({"x": cx, "y": cy, "w": t.shape[1] / 0.25, "h": t.shape[0] / 0.25, "kind": "ghost",
                            "pink": 0.0, "purple": 0.0, "blue": 1.0, "skin": 0.0, "green": 0.0})
            r[max(0, ly - t.shape[0]):ly + t.shape[0], max(0, lx - t.shape[1]):lx + t.shape[1]] = 0
        return out

    def _pick_player(self, cands, W, H):
        best, best_score = None, -1e9
        for b in cands:
            # чем ближе к персонажу «по цвету» (кожа ~0.29, розовый ~0.2), тем лучше
            score = -abs(b["skin"] - 0.29) * 3 - abs(b["pink"] - 0.2) * 3
            if self.prev_player:
                d = np.hypot(wdx(self.prev_player[0], b["x"], W), self.prev_player[1] - b["y"])
                score -= d / (0.25 * H)
            if score > best_score:
                best, best_score = b, score
        return best

    def forget(self):
        self.prev_player = None


def merge_overlapping(plats):
    """Треснувшая коричневая платформа иногда находится двумя наложенными рамками.
    Если рамки то сливаются, то нет, центр прыгает и платформа «едет» — бот начинает
    ждать её, как движущуюся. Склеиваем такие рамки в одну."""
    out = []
    for pl in sorted(plats, key=lambda q: q["x"]):
        m = next((q for q in out if abs(q["y"] - pl["y"]) < 22
                  and abs(q["x"] - pl["x"]) < (q["w"] + pl["w"]) / 2), None)
        if m is None:
            out.append(dict(pl))
            continue
        lo = min(m["x"] - m["w"] / 2, pl["x"] - pl["w"] / 2)
        hi = max(m["x"] + m["w"] / 2, pl["x"] + pl["w"] / 2)
        m.update(x=(lo + hi) / 2, w=hi - lo, y=min(m["y"], pl["y"]),
                 type="b" if "b" in (m["type"], pl["type"]) else m["type"])
    return out


def wdx(a, b, W):
    """Кратчайшее смещение по X с учётом прохода сквозь край экрана."""
    d = b - a
    if d > W / 2:
        d -= W
    elif d < -W / 2:
        d += W
    return d


# ============================================================================
# Слежение: прокрутка, скорость, прыжки и входы для сети
# ============================================================================
PX_PER_M = 20.5      # пикселей подъёма на игровой метр при высоте окна 1080
SIM_APEX = 196.0      # высота прыжка в симуляторе, px
SIM_PERIOD = 59.5     # отскок на ряд вверх в симуляторе, тики (в игре это self.period ≈ 0.585 с)
SIM_W = 400.0
SIM_MAXVX = 2.82    # должна совпадать с MAXVX в pretrain/sim.js
SIM_MOVE_SPEED = 0.49  # скорость движущихся платформ в симуляторе (MOVE_SPEED)
COOLDOWN_S = 0.35


class Tracker:
    def __init__(self, W, H):
        self.W, self.H = W, H
        self.scroll = 0.0
        self.prev_plats = None
        self.prev_t = None
        self.prev_p = None       # (x, мировой y) персонажа
        self.vx = self.vy = 0.0
        self.base = None         # (x, мировой y) платформы, от которой оттолкнулись
        self.start_wy = None
        self.max_h = 0.0
        # Оценки высоты и длительности прыжка (по записи игры ~0.14 высоты экрана и ~0.6 с);
        # уточняются по ходу игры
        self.apex = 0.14 * H
        self.period = 0.6
        self.falling = False
        self.prev_vy_raw = None
        self.bounces = []
        self.flight = []         # (t, мировой y) персонажа с последнего отскока
        self.vx_raw = 0.0
        self.last_move = 0
        self.rises = []
        self.min_wy_since_bounce = None
        self.last_throw = -9.0
        self.throws = 0
        self.kills = 0
        self.tracks = []         # враги, за которыми следим: x, y, сколько кадров видели, вид
        self.dead_marks = []     # где и когда засчитали убийство (x, мировой y, t)
        self.last_seen = time.time()

    def _scroll_delta(self, plats):
        if not self.prev_plats:
            return 0.0
        tol = 0.012 * self.W
        deltas = []
        for p in plats:
            best = None
            for q in self.prev_plats:
                dy = p["y"] - q["y"]
                if abs(p["x"] - q["x"]) < tol and -2 <= dy < 0.12 * self.H and (best is None or dy < best):
                    best = dy
            if best is not None:
                deltas.append(best)
        if len(deltas) < 2:
            return 0.0
        return max(0.0, float(np.median(deltas)))

    def update(self, det, t):
        W, H = self.W, self.H
        ds = self._scroll_delta(det["plats"])
        self.scroll += ds
        dt = (t - self.prev_t) if self.prev_t else 1 / 30
        dt = max(dt, 1e-3)
        self._plat_speeds(det["plats"], ds, dt)
        self.prev_plats = det["plats"]
        self.prev_t = t

        self._track_enemies(det["enemies"], t)

        p = det["player"]
        if p is None:
            return
        self.last_seen = t
        wy = p["y"] - self.scroll
        if self.prev_p is not None:
            vx = wdx(self.prev_p[0], p["x"], W) / dt
            vy = (wy - self.prev_p[1]) / dt
            self.vx = 0.5 * self.vx + 0.5 * vx
            self.vy = 0.5 * self.vy + 0.5 * vy
            # Отскок: падали — и резко полетели вверх. Смотрим на сырую скорость:
            # сглаженная меняет знак слишком плавно, и отскок терялся
            # Если запрыгнул на платформу у самой вершины прыжка, падения почти нет —
            # поэтому отскоком считаем и резкий рывок вверх
            jerk = self.prev_vy_raw is not None and self.prev_vy_raw - vy > 0.3 * H and vy < -0.15 * H
            recent = self.bounces and t - self.bounces[-1] < 0.2
            if vy > 0.1 * H:
                self.falling = True
            elif vy < -0.1 * H and (self.falling or jerk) and not recent:
                self.falling = False
                self._on_bounce(det, p, wy, t)
            self.prev_vy_raw = vy
            self.vx_raw = vx
        self.prev_p = (p["x"], wy)
        if not self.flight or self.flight[-1][0] != t:
            self.flight = (self.flight + [(t, wy)])[-5:]
        if self.start_wy is None:
            self.start_wy = wy
            self.base = (p["x"], wy + p["h"] / 2)
        self.max_h = max(self.max_h, self.start_wy - wy)
        if self.min_wy_since_bounce is None or wy < self.min_wy_since_bounce:
            self.min_wy_since_bounce = wy

    def _plat_speeds(self, plats, ds, dt):
        """Скорость каждой платформы по горизонтали: движущиеся ездят туда-обратно ~60 px/с.
        Сглаживаем, а дрожание рамки на 1–2 px (до ~25 px/с) считаем нулём."""
        for pl in plats:
            pl["vx"] = 0.0
            if not self.prev_plats:
                continue
            best = None
            for q in self.prev_plats:
                if abs(pl["y"] - (q["y"] + ds)) <= 3:
                    dx = wdx(q["x"], pl["x"], self.W)
                    if abs(dx) <= 20 and (best is None or abs(dx) < abs(best[0])):
                        best = (dx, q)
            if best:
                raw = best[0] / dt
                v = 0.7 * best[1].get("vs", 0.0) + 0.3 * raw
                pl["vs"] = v
                pl["vx"] = v if abs(v) > 25 else 0.0

    def _track_enemies(self, enemies, t):
        """Убийство засчитываем, только если враг, которого видели хотя бы 4 кадра подряд,
        исчез посреди экрана вскоре после броска. Иначе мигание рамок считалось убийствами."""
        W, H = self.W, self.H
        new = []
        used = set()
        for e in enemies:
            best = None
            for i, tr in enumerate(self.tracks):
                if i in used:
                    continue
                d = abs(wdx(tr["x"], e["x"], W)) + abs(tr["y"] - e["y"])
                if d < 0.12 * W and (best is None or d < best[0]):
                    best = (d, i)
            if best:
                used.add(best[1])
                tr = self.tracks[best[1]]
                new.append({"x": e["x"], "y": e["y"], "n": tr["n"] + 1, "miss": 0, "kind": e["kind"]})
            else:
                new.append({"x": e["x"], "y": e["y"], "n": 1, "miss": 0, "kind": e["kind"]})
                # Враг, «убитый» недавно, снова на том же месте — значит, рамка просто мигнула
                wy = e["y"] - self.scroll
                for m in self.dead_marks:
                    if t - m[2] < 4 and abs(wdx(m[0], e["x"], W)) < 0.1 * W and abs(m[1] - wy) < 0.08 * H:
                        self.dead_marks.remove(m)
                        self.kills = max(0, self.kills - 1)
                        break
        for i, tr in enumerate(self.tracks):
            if i in used:
                continue
            tr["miss"] += 1
            if tr["miss"] <= 2:  # пару кадров прощаем — рамка могла мигнуть
                new.append(tr)
            elif (tr["n"] >= 4 and tr["kind"] != "hole" and 0.12 * H < tr["y"] < 0.85 * H
                  and t - self.last_throw < 0.8 and self.kills < self.throws):
                self.kills += 1
                self.dead_marks.append((tr["x"], tr["y"] - self.scroll, t))
        self.tracks = new

    def _on_bounce(self, det, p, wy, t):
        feet = p["y"] + p["h"] / 2
        best = None
        for pl in det["plats"]:
            d = abs(pl["y"] - feet)
            if abs(wdx(p["x"], pl["x"], self.W)) < pl["w"] / 2 + p["w"] / 2 and d < 0.06 * self.H:
                if best is None or d < best[0]:
                    best = (d, pl)
        base_y = (best[1]["y"] if best else feet) - self.scroll
        if self.base is not None and self.min_wy_since_bounce is not None:
            rise = self.base[1] - self.min_wy_since_bounce - p["h"] / 2
            if 0.08 * self.H < rise < 0.35 * self.H:
                self.rises = (self.rises + [rise])[-12:]
                self.apex = float(np.median(self.rises))
        if self.bounces:
            per = t - self.bounces[-1]
            if 0.35 < per < 1.2:
                self.periods = (getattr(self, "periods", []) + [per])[-12:]
                self.period = float(np.median(self.periods))
        self.bounces = (self.bounces + [t])[-13:]
        self.base = (best[1]["x"] if best else p["x"], base_y)
        self.min_wy_since_bounce = wy
        self.flight = [(t, wy)]

    def gravity(self):
        """Гравитация в px/с², выведенная из высоты и длительности прыжка (как в симуляторе)."""
        tick = self.period / SIM_PERIOD
        return SIM_G / (SIM_APEX / self.apex) / (tick * tick)

    def phys_vy(self, t):
        """Вертикальная скорость сейчас: по точкам с последнего отскока при известной гравитации.
        Сглаженная скорость отстаёт на кадр-два, и сразу после отскока ещё «падает»."""
        g = self.gravity()
        pts = getattr(self, "flight", [])
        if len(pts) < 2:
            return -math.sqrt(2 * g * self.apex) + (g * (t - pts[0][0]) if pts else 0.0)
        tn = pts[-1][0]
        xs = np.array([ti - tn for ti, _ in pts])
        ys = np.array([yi - g / 2 * x * x for (_, yi), x in zip(pts, xs)])
        n, sx, sy, sxx, sxy = len(xs), xs.sum(), ys.sum(), (xs * xs).sum(), (xs * ys).sum()
        den = n * sxx - sx * sx
        v = (n * sxy - sx * sy) / den if den > 1e-9 else self.vy
        return float(v + g * (t - tn))

    def inputs(self, det, t):
        """26 входов в тех же единицах, что и в симуляторе (порядок — как в pretrain/sim.js sense())."""
        W, H = self.W, self.H
        p = det["player"]
        kv = SIM_APEX / self.apex              # реальные px по вертикали -> px симулятора
        tick = self.period / SIM_PERIOD        # секунд в одном тике симулятора
        vx_sim = self.vx * (SIM_W / W) * tick
        vy_sim = self.vy * kv * tick
        inp = [vx_sim / SIM_MAXVX, vy_sim / 15.0]
        vel = lambda pl: pl.get("vx", 0.0) * (SIM_W / W) * tick / SIM_MOVE_SPEED
        feet = p["y"] + p["h"] / 2
        base_wy = self.base[1] if self.base else feet - self.scroll
        # После пружины или ракеты персонаж улетает много выше обычного прыжка:
        # платформа старта уже далеко внизу, и цели нужно искать над ним, а не над ней
        if base_wy - (feet - self.scroll) > 1.1 * self.apex:
            base_wy = feet - self.scroll + 0.3 * self.apex
        # Коричневые «ломающиеся» платформы в этой игре сразу восстанавливаются — на них можно прыгать
        nxt = [pl for pl in det["plats"] if pl["y"] - self.scroll < base_wy - 0.01 * H]
        nxt.sort(key=lambda pl: -pl["y"])
        for i in range(3):
            if i < len(nxt):
                pl = nxt[i]
                inp += [wdx(p["x"], pl["x"], W) / (W / 2), (pl["y"] - feet) * kv / 300.0, vel(pl), 1.0]
            else:
                inp += [0.0, 0.0, 0.0, 0.0]
        # Ближайшая платформа под ногами: куда можно спастись, если промахнулся мимо цели,
        # и на которой можно переждать, если она едет к нужной
        below = [pl for pl in det["plats"] if pl["y"] >= feet]
        if below:
            pl = min(below, key=lambda q: q["y"])
            inp += [wdx(p["x"], pl["x"], W) / (W / 2), (pl["y"] - feet) * kv / 300.0, 1.0, vel(pl)]
        else:
            inp += [0.0, 0.0, 0.0, 0.0]
        enemy = self.nearest_enemy(det)
        if enemy:
            inp += [wdx(p["x"], enemy["x"], W) / (W / 2), (enemy["y"] - p["y"]) * kv / 300.0, 1.0]
        else:
            inp += [0.0, 0.0, 0.0]
        # Ближайшая чёрная дыра — её нужно облетать
        holes = [e for e in det["enemies"] if e.get("kind") == "hole"]
        if holes:
            hl = min(holes, key=lambda e: np.hypot(wdx(p["x"], e["x"], W), e["y"] - p["y"]))
            inp += [wdx(p["x"], hl["x"], W) / (W / 2), (hl["y"] - p["y"]) * kv / 300.0, 1.0]
        else:
            inp += [0.0, 0.0, 0.0]
        inp += [1.0 if t - self.last_throw > COOLDOWN_S else 0.0, 1.0]
        return np.array(inp, dtype=np.float64), nxt[:3], enemy

    def nearest_enemy(self, det):
        p = det["player"]
        best, bd = None, 1e9
        for e in det["enemies"]:
            if e.get("kind") == "hole":  # чёрную дыру не убить — бросать в неё бессмысленно
                continue
            d = np.hypot(wdx(p["x"], e["x"], self.W), e["y"] - p["y"])
            if d < bd:
                best, bd = e, d
        return best

    def fitness(self):
        return self.max_h * SIM_APEX / self.apex + 150 * self.kills - 3 * self.throws

    def height_label(self):
        return int(self.max_h)

    def meters(self):
        # Сверено со счётчиком игры: старт показывает 7 м, дальше ~20.5 px подъёма на метр
        return 7 + self.max_h * (1080.0 / self.H) / PX_PER_M


# ============================================================================
# Автопилот: тот же «учитель», что в симуляторе (pretrain/teacher.js), но на настоящей игре
# ============================================================================
AUTOPILOT = "autopilot"  # вместо генома: играть физическим планировщиком
SIM_G = 0.32          # гравитация симулятора, px/тик²
SIM_HOLE_R = 34.0
SPRING_BONUS = 400.0  # пружина уносит на несколько рядов вверх — берём её, если долетаем


def _land_time(vy, dy):
    """Через сколько тиков ноги, двигаясь вниз, окажутся на dy ниже текущего места (как в teacher.js)."""
    a, b, c = SIM_G / 2, vy + SIM_G / 2, -dy
    disc = b * b - 4 * a * c
    if disc < 0:
        return None
    t = (-b + math.sqrt(disc)) / (2 * a)
    return t if t > 0 else None


def _reach(vx, d, t):
    v, s, n = vx, 0.0, int(t)
    for _ in range(n):
        v += (d * SIM_MAXVX - v) * 0.25
        s += v * d
    return s


def plan(tr, det, t, springs=True, latency=0.0):
    """Решение физикой, без нейросети. Всё переводим в единицы симулятора: там этот учитель
    проверен, в том числе с задержкой реакции и шумом распознавания.
    latency — сколько секунд прошло с момента снимка экрана плюс запаздывание игры:
    на это время положение персонажа досчитываем вперёд.
    Возвращает (движение, бросок, цель)."""
    W, H = tr.W, tr.H
    p = det["player"]
    sx = SIM_W / W
    kv = SIM_APEX / tr.apex
    tick = tr.period / SIM_PERIOD
    vx = tr.vx_raw * sx * tick
    vy = tr.phys_vy(t) * kv * tick
    feet = p["y"] + p["h"] / 2
    holes = [e for e in det["enemies"] if e.get("kind") == "hole"]
    base_wy = tr.base[1] if tr.base else feet - tr.scroll

    # Платформы относительно ног, в px симулятора (dy > 0 — ниже ног)
    rel = []
    for pl in det["plats"]:
        spring = pl.get("spring") if springs else None
        cx, half = (spring[0], spring[1] * sx / 2) if spring else (pl["x"], pl["w"] * sx / 2)
        rel.append((pl, wdx(p["x"], cx, W) * sx, (pl["y"] - feet) * kv, half, bool(spring),
                    abs(wdx(p["x"], pl["x"], W) * sx), pl["w"] * sx / 2))

    # Досчитываем полёт вперёд на время задержки, с отскоками от платформ
    qx = qy = 0.0
    n = int(round(latency / tick))
    bounced = None
    for _ in range(min(n, 30)):
        vx += (tr.last_move * SIM_MAXVX - vx) * 0.25
        qx += vx
        oy = qy
        vy += SIM_G
        qy += vy
        if vy > 0:
            for r in rel:
                pl, _, dy = r[0], r[1], r[2]
                px = wdx(p["x"], pl["x"], W) * sx
                ddx = px - qx
                ddx = (ddx + SIM_W / 2) % SIM_W - SIM_W / 2
                if oy <= dy <= qy and abs(ddx) < r[6] + 13:
                    vy = -19.0 if (r[4] and abs(((r[1] - qx) + SIM_W / 2) % SIM_W - SIM_W / 2) < r[3] + 10) else -11.2
                    qy = dy
                    bounced = pl
                    break
    if bounced is not None:
        base_wy = bounced["y"] - tr.scroll
    base_pl = bounced
    if base_pl is None and tr.base:
        cand = [pl for pl in det["plats"] if abs(pl["y"] - tr.scroll - base_wy) < 0.015 * H
                and abs(wdx(pl["x"], tr.base[0], W)) < 0.2 * W]
        if cand:
            base_pl = min(cand, key=lambda pl: abs(wdx(pl["x"], tr.base[0], W)))

    prev = getattr(tr, "plan_target", None)
    best = up = None
    for pl, d0, dy0, half, spring, _, _ in rel:
        dy = dy0 - qy
        d = ((d0 - qx) + SIM_W / 2) % SIM_W - SIM_W / 2
        if dy < -1 and vy > 0:                # выше ног, а уже падаем — не достать
            continue
        if _land_time(vy, dy - 12) is None:   # в высшей точке нужен запас по высоте
            continue
        lt = _land_time(vy, dy)
        if lt is None or lt < 2:
            continue
        # Где платформа будет, когда долетим (движущиеся ездят туда-обратно, поэтому не дальше ~45 px)
        d += max(-45.0, min(45.0, pl.get("vx", 0.0) * sx * tick * (lt + n)))
        tol = half + 7
        cx = pl["spring"][0] if spring else pl["x"]
        danger = any(abs(wdx(hl["x"], cx, W)) * sx < max(SIM_HOLE_R, hl["w"] * sx / 2) + 22
                     and (pl["y"] - 230 / kv) < hl["y"] < pl["y"] + 20 / kv for hl in holes)
        need = max(0.0, abs(d) - tol)
        margin = _reach(vx, 1 if d >= 0 else -1, lt) - need
        # Уже выбранную цель держим, пока до неё можно дотянуться: из-за задержки расчёт
        # чуть пессимистичен, и без этого бот метался между целями (и между двумя
        # платформами на одной высоте) и падал мимо обеих
        mine = prev is not None and abs(wdx(prev[0], pl["x"], W)) < 0.06 * W and abs(prev[1] - (pl["y"] - tr.scroll)) < 0.03 * H
        if margin >= (-10 if mine else 8) and not danger:
            score = -dy + (SPRING_BONUS if spring else 0.0) + (40.0 if mine else 0.0)
        else:
            score = -1e6 + margin
        if best is None or score > best[0]:
            best = (score, pl, d, half)
        if pl["y"] - tr.scroll < base_wy - 1 / kv:
            m = margin - (20 if danger else 0)
            if up is None or m > up[0]:
                up = (m, pl, d, half)
    # Долетаем надёжно только обратно на свою платформу — пробуем ближайшую по шансам выше
    # (на движущейся лучше подождать, пока она подвезёт к нужной)
    if best and base_pl is not None and best[1] is base_pl and not base_pl.get("vx") and up and up[0] > -25:
        best = (0.0,) + up[1:]
    move, target = 0, None
    if best:
        _, target, d, half = best
        tr.plan_target = (target["x"], target["y"] - tr.scroll)
        after = d - 3 * vx  # отпустим клавишу — ещё немного проскользим
        if abs(after) > max(4.0, half - 10):
            move = 1 if after > 0 else -1
    # Чёрная дыра на пути вверх — уходим в сторону и к ней не приближаемся
    rise = vy * vy / (2 * SIM_G) if vy < 0 else 0.0
    for hl in holes:
        r = max(SIM_HOLE_R, hl["w"] * sx / 2)
        dx = ((wdx(p["x"], hl["x"], W) * sx - qx) + SIM_W / 2) % SIM_W - SIM_W / 2
        dyh = (hl["y"] - p["y"]) * kv - qy
        if dyh >= 30 or dyh <= -(rise + 30):
            continue
        away = -1 if dx > 0 else 1
        if abs(dx) < r + 18:
            move = away
        elif abs(dx) < r + 45 and move == -away:
            move = 0
    enemy = tr.nearest_enemy(det)
    throw = enemy is not None and t - tr.last_throw > COOLDOWN_S
    return move, throw, target


# ============================================================================
# Экран и управление
# ============================================================================
class Screen:
    def __init__(self, region=None):
        import mss
        self.sct = mss.mss()
        self.region = region

    def monitor(self, index=1):
        m = self.sct.monitors[index]
        return np.array(self.sct.grab(m))[:, :, :3], m

    def grab(self):
        r = self.region
        img = np.array(self.sct.grab({"left": r["left"], "top": r["top"], "width": r["width"], "height": r["height"]}))
        return img[:, :, :3]


def find_game_regions(img):
    """Кандидаты на область игры: светлые вертикальные полосы между тёмными полями Telegram.
    Возвращает несколько вариантов — какой из них игра, проверяет поиск платформ."""
    col = img.astype(np.int16).mean(axis=(0, 2))
    out = []
    for frac in (0.5, 0.35, 0.65):
        thr = col.min() + (col.max() - col.min()) * frac
        bright = list(col > thr) + [False]
        start = None
        for i, v in enumerate(bright):
            if v and start is None:
                start = i
            elif not v and start is not None:
                x0, x1 = start, i
                start = None
                if x1 - x0 < 150:
                    continue
                rows = img[:, x0:x1].astype(np.int16).mean(axis=(1, 2))
                if rows.max() - rows.min() > 60:
                    ys = np.where(rows > (rows.min() + rows.max()) / 2)[0]
                else:
                    ys = np.arange(len(rows))
                if len(ys) < 200:
                    continue
                r = {"left": int(x0), "top": int(ys[0]), "width": int(x1 - x0), "height": int(ys[-1] - ys[0] + 1)}
                if r not in out:
                    out.append(r)
    return out


def find_game_region(img):
    """Лучший кандидат: тот, где нашлось больше всего платформ."""
    best, best_n = None, 2
    for r in find_game_regions(img):
        crop = img[r["top"]:r["top"] + r["height"], r["left"]:r["left"] + r["width"]]
        n = len(Detector().detect(crop)["plats"])
        if n > best_n:
            best, best_n = r, n
    return best


class Controls:
    def __init__(self, region, dry=False):
        self.region = region
        self.dry = dry
        self.held = 0
        if dry:
            return
        if sys.platform == "win32":
            import pydirectinput
            pydirectinput.PAUSE = 0
            pydirectinput.FAILSAFE = False
            self.lib = "pdi"
            self.pdi = pydirectinput
        else:
            from pynput.keyboard import Controller as K
            from pynput.mouse import Controller as M, Button
            self.lib = "pynput"
            self.kb, self.mouse, self.Button = K(), M(), Button

    def _key(self, key, down):
        if self.lib == "pdi":
            (self.pdi.keyDown if down else self.pdi.keyUp)(key)
        else:
            (self.kb.press if down else self.kb.release)(key)

    def move(self, d):
        """Игра двигает персонажа по повторяющимся нажатиям, как при зажатой клавише,
        поэтому пока клавиша «зажата», шлём нажатие на каждом кадре."""
        if self.dry:
            return
        if d == self.held:
            if d == -1:
                self._key("a", True)
            elif d == 1:
                self._key("d", True)
            return
        if self.held == -1:
            self._key("a", False)
        if self.held == 1:
            self._key("d", False)
        if d == -1:
            self._key("a", True)
        if d == 1:
            self._key("d", True)
        self.held = d

    def click(self, x, y):
        """x, y — координаты внутри области игры."""
        if self.dry:
            return
        sx, sy = int(self.region["left"] + x), int(self.region["top"] + y)
        if self.lib == "pdi":
            self.pdi.click(sx, sy)
        else:
            self.mouse.position = (sx, sy)
            self.mouse.click(self.Button.left)

    def release(self):
        self.move(0)


class Hotkeys:
    """F8 — отметка (в setup), F9 — пауза, F10 — выход."""

    def __init__(self):
        self.paused = False
        self.quit = False
        self.marks = 0
        self.finish = False
        try:
            from pynput import keyboard
        except ImportError:
            print("pynput не установлен — горячие клавиши не работают")
            return

        def on_press(key):
            if key == keyboard.Key.f8:
                self.marks += 1
            elif key == keyboard.Key.f9:
                self.paused = not self.paused
                self.finish = True
                print("Пауза" if self.paused else "Продолжаю")
            elif key == keyboard.Key.f10:
                self.quit = True

        self.listener = keyboard.Listener(on_press=on_press)
        self.listener.daemon = True
        self.listener.start()

    def wait_mark(self):
        start = self.marks
        while self.marks == start and not self.quit:
            time.sleep(0.05)


def mouse_position():
    from pynput.mouse import Controller
    return Controller().position


# ============================================================================
# Эволюция
# ============================================================================
# Версия смысла входов сети: при её смене старый population.json не подходит и обучение начинается заново
POP_VERSION = 6


class Population:
    """Каждая сеть играет одну попытку. После поколения ELITE лучших переходят как есть
    (и переигрывают — так везение отсеивается), остальные — мутированные копии лучших."""

    SIZE, ELITE, PARENTS = 12, 3, 6
    MUT_RATE, MUT_SIGMA = 0.2, 0.3

    def __init__(self):
        self.gen = 1
        self.idx = 0
        self.history = []
        self.best = None
        self.best_fit = -1e9
        self.genomes = []
        self.fits = []
        carry = []
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, encoding="utf-8") as f:
                s = json.load(f)
            if s.get("ng") == NG and s.get("ver") == POP_VERSION:
                self.gen, self.idx, self.history = s["gen"], s.get("idx", 0), s.get("history", [])
                self.best_fit = s.get("best_fit", -1e9)
                self.best = np.array(s["best"]) if s.get("best") else None
                self.genomes = [np.array(g) for g in s["genomes"]]
                self.fits = s.get("fits", [])
                print(f"Продолжаю обучение: поколение {self.gen}, сеть {self.idx + 1}")
            elif s.get("ng") == NG:
                # Устройство сети то же, поменялись только единицы входов: лучшие сети, обученные
                # в игре, берём с собой — пусть соревнуются с новыми из симулятора
                carry = ([np.array(s["best"])] if s.get("best") else []) + [np.array(g) for g in s["genomes"][:3]]
                print(f"Бот обновился: беру лучшие сети из прошлого обучения ({len(carry)} шт.) и новые из симулятора")
            else:
                print("Сохранённое обучение от старой версии бота не подходит — начинаю заново")
        if not self.genomes:
            seeds = []
            if os.path.exists(PRETRAINED_PATH):
                with open(PRETRAINED_PATH, encoding="utf-8") as f:
                    pre = json.load(f)
                if pre.get("ng") == NG:
                    seeds = [np.array(g) for g in pre["genomes"]]
                    print(f"Старт с {len(seeds)} сетей, предобученных в симуляторе")
            if not seeds:
                print("Старт с нуля: случайные сети")
            self.genomes = (carry + seeds)[:self.SIZE]
            while len(self.genomes) < self.SIZE:
                if seeds:
                    self.genomes.append(self.mutate(random.choice(seeds)))
                else:
                    self.genomes.append(np.random.randn(NG) * 0.6)

    def mutate(self, g):
        c = g.copy()
        m = np.random.rand(NG) < self.MUT_RATE
        c[m] += np.random.randn(int(m.sum())) * self.MUT_SIGMA
        return c

    def current(self):
        return self.genomes[self.idx]

    def report(self, fit, height, kills):
        self.fits.append(fit)
        if fit > self.best_fit:
            self.best_fit, self.best = fit, self.genomes[self.idx].copy()
        self.idx += 1
        if self.idx >= len(self.genomes):
            self.evolve()
        self.save()

    def evolve(self):
        order = np.argsort(self.fits)[::-1]
        self.history.append({"gen": self.gen, "best": float(self.fits[order[0]]),
                             "avg": float(np.mean(self.fits))})
        print(f"=== Поколение {self.gen}: лучший {self.fits[order[0]]:.0f}, среднее {np.mean(self.fits):.0f}")
        parents = [self.genomes[i] for i in order[:self.PARENTS]]
        nxt = [self.genomes[i] for i in order[:self.ELITE]]
        while len(nxt) < self.SIZE:
            nxt.append(self.mutate(random.choice(parents)))
        self.genomes, self.fits, self.idx = nxt, [], 0
        self.gen += 1

    def save(self):
        data = {"ng": NG, "ver": POP_VERSION, "gen": self.gen, "idx": self.idx, "history": self.history,
                "best_fit": self.best_fit, "best": self.best.tolist() if self.best is not None else None,
                "genomes": [g.tolist() for g in self.genomes], "fits": self.fits}
        tmp = STATE_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, STATE_PATH)


# ============================================================================
# Одна попытка
# ============================================================================
def draw_debug(img, det, tr, nxt, enemy, move, throw, info=""):
    out = img.copy()
    H, W = out.shape[:2]
    for pl in det["plats"]:
        x0 = int(pl["x"] - pl["w"] / 2)
        cv2.rectangle(out, (x0, int(pl["y"])), (int(x0 + pl["w"]), int(pl["y"] + 10)), (60, 160, 60), 2)
    for i, pl in enumerate(nxt or []):
        cv2.putText(out, str(i + 1), (int(pl["x"]) - 5, int(pl["y"]) - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 120, 0), 2)
    for e in det["enemies"]:
        cv2.rectangle(out, (int(e["x"] - e["w"] / 2), int(e["y"] - e["h"] / 2)),
                      (int(e["x"] + e["w"] / 2), int(e["y"] + e["h"] / 2)), (40, 40, 220), 2)
    p = det["player"]
    if p:
        cv2.rectangle(out, (int(p["x"] - p["w"] / 2), int(p["y"] - p["h"] / 2)),
                      (int(p["x"] + p["w"] / 2), int(p["y"] + p["h"] / 2)), (220, 120, 20), 2)
        if enemy and throw:
            cv2.line(out, (int(p["x"]), int(p["y"])), (int(enemy["x"]), int(enemy["y"])), (40, 40, 220), 1)
    if tr and tr.base:
        by = int(tr.base[1] + tr.scroll)
        cv2.line(out, (int(tr.base[0]) - 30, by), (int(tr.base[0]) + 30, by), (200, 60, 200), 2)
    arrow = {-1: "<- A", 0: ".", 1: "D ->"}[move]
    lines = [f"{arrow}  {'CLICK' if throw else ''}", info]  # cv2 не рисует кириллицу
    if tr:
        lines.append(f"h={tr.height_label()} kills={tr.kills} jump={tr.apex:.0f}px/{tr.period:.2f}s")
    for i, l in enumerate(lines):
        cv2.putText(out, l, (8, H - 60 + i * 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (20, 20, 20), 2)
    return out


def play_run(screen, ctl, hk, genome, show=True, info="", act=True, on_frame=None):
    det_ = Detector()
    region = screen.region
    tr = Tracker(region["width"], region["height"])
    t_start = time.time()
    frames = 0
    while not hk.quit:
        if hk.paused:
            ctl.release()
            time.sleep(0.1)
            tr.prev_t = None
            continue
        t = time.time()
        img = screen.grab()
        det = det_.detect(img)
        tr.update(det, t)
        move, throw, nxt, enemy, steer, inp = 0, False, [], None, 0.0, None
        if det["player"] is not None:
            inp, nxt, enemy = tr.inputs(det, t)
            if genome is AUTOPILOT:
                # снимок сделан в момент t; до игры нажатие дойдёт ещё через ~кадр
                move, throw, tgt = plan(tr, det, t, latency=time.time() - t + 0.03)
                nxt = [tgt] if tgt is not None else []
                if not tr.bounces and t - t_start < 3:
                    move = 0
            elif genome is not None:
                move, throw, steer = decide(genome, inp)
                # Попытка начинается с персонажа в воздухе над стартовой платформой:
                # до первого приземления стоим на месте, иначе он пролетает мимо неё
                if not tr.bounces and t - t_start < 3:
                    move = 0
            tr.last_move = move
            if act:
                ctl.move(move)
                if throw and enemy and t - tr.last_throw > COOLDOWN_S:
                    ctl.click(enemy["x"], enemy["y"])
                    tr.last_throw = t
                    tr.throws += 1
        else:
            ctl.release()
        frames += 1
        if on_frame is not None:
            fps = frames / max(t - t_start, 1e-3)
            on_frame({"t": t, "img": img, "det": det, "tr": tr, "nxt": nxt, "enemy": enemy, "move": move,
                      "throw": throw, "steer": float(steer), "inp": inp, "info": f"{info} {fps:.0f} fps",
                      "proc_ms": (time.time() - t) * 1000})
        elif show:
            fps = frames / max(t - t_start, 1e-3)
            cv2.imshow(DEBUG_WINDOW, draw_debug(img, det, tr, nxt, enemy, move, throw, f"{info} {fps:.0f} fps"))
            if cv2.waitKey(1) & 0xFF == 27:
                hk.quit = True
        # Смерть: персонаж пропал или улетел за нижний край
        p = det["player"]
        if t - tr.last_seen > 0.8 and t - t_start > 2:
            break
        # Стартовая платформа бывает у самого нижнего края, поэтому «упал» — только когда
        # персонаж целиком ушёл за край, а не когда ноги коснулись низа экрана
        if p is not None and p["y"] - p["h"] / 2 > 0.97 * region["height"] and tr.vy > 0:
            break
    ctl.release()
    return tr


def restart(screen, ctl, hk, cfg):
    """Жмёт «играть снова» и ждёт, пока на экране появятся персонаж и платформы."""
    det = Detector()
    for attempt in range(5):
        time.sleep(cfg.get("restart_delay", 1.5))
        for (rx, ry) in cfg.get("restart_clicks", []):
            ctl.click(rx * screen.region["width"], ry * screen.region["height"])
            time.sleep(0.6)
        ok_since = None
        t0 = time.time()
        while time.time() - t0 < 6 and not hk.quit:
            d = det.detect(screen.grab())
            if d["player"] is not None and len(d["plats"]) >= 3:
                ok_since = ok_since or time.time()
                if time.time() - ok_since > 0.4:
                    return True
            else:
                ok_since = None
            time.sleep(0.05)
        if not cfg.get("restart_clicks"):
            print("Начните новую игру вручную (кнопка рестарта не настроена — см. python bot.py setup)")
    return False


# ============================================================================
# Команды
# ============================================================================
def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit("Нет config.json. Сначала запустите: python bot.py setup")
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def cmd_setup(args):
    hk = Hotkeys()
    scr = Screen()
    print("1) Откройте игру в Telegram и начните играть (или поставьте на паузу).")
    print("   Нажмите F8, когда игра видна на экране.")
    hk.wait_mark()
    img, mon = scr.monitor(args.monitor)
    reg = find_game_region(img)
    if reg is None:
        sys.exit("Не нашёл область игры. Укажите её вручную в config.json (left/top/width/height).")
    reg = {"left": reg["left"] + mon["left"], "top": reg["top"] + mon["top"],
           "width": reg["width"], "height": reg["height"]}
    print(f"   Область игры: {reg}")
    scr.region = reg
    shot = scr.grab()
    det = Detector().detect(shot)
    print(f"   Нашёл платформ: {len(det['plats'])}, персонаж: {'да' if det['player'] else 'нет'}, врагов: {len(det['enemies'])}")
    cv2.imwrite(os.path.join(HERE, "setup_check.png"), draw_debug(shot, det, None, [], None, 0, False))
    print("   Картинка с распознаванием сохранена в setup_check.png — проверьте её.")

    print("2) Дайте персонажу упасть. На экране проигрыша наведите мышь на кнопку")
    print("   «Играть снова» и нажмите F8. Если нужно несколько кликов — F8 на каждой кнопке.")
    print("   Когда закончите — F9.")
    clicks = []
    hk.finish = False
    last = hk.marks
    while not hk.finish and not hk.quit:
        if hk.marks != last:
            last = hk.marks
            mx, my = mouse_position()
            rx, ry = (mx - reg["left"]) / reg["width"], (my - reg["top"]) / reg["height"]
            clicks.append([round(rx, 4), round(ry, 4)])
            print(f"   Клик №{len(clicks)}: {clicks[-1]} (доля ширины/высоты игры)")
        time.sleep(0.05)
    hk.paused = False
    cfg = {"region": reg, "restart_clicks": clicks, "restart_delay": 1.5}
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    print(f"Готово, настройки в {CONFIG_PATH}. Дальше: python bot.py debug")


def cmd_debug(args):
    if args.image:
        img = cv2.imread(args.image)
        if img is None:
            sys.exit("Не удалось открыть картинку")
        reg = find_game_region(img)
        if reg:
            img = img[reg["top"]:reg["top"] + reg["height"], reg["left"]:reg["left"] + reg["width"]]
        det = Detector().detect(img)
        tr = Tracker(img.shape[1], img.shape[0])
        tr.update(det, time.time())
        nxt, enemy, move, throw = [], None, 0, False
        if det["player"]:
            inp, nxt, enemy = tr.inputs(det, time.time())
            print("Входы сети:", np.round(inp, 2).tolist())
        print(f"Платформ: {len(det['plats'])}, персонаж: {det['player']}, врагов: {len(det['enemies'])}")
        out = args.out or os.path.join(HERE, "debug_image.png")
        cv2.imwrite(out, draw_debug(img, det, tr, nxt, enemy, move, throw))
        print("Сохранил", out)
        return
    cfg = load_config()
    scr = Screen(cfg["region"])
    hk = Hotkeys()
    ctl = Controls(cfg["region"], dry=True)
    print("Режим просмотра: бот ничего не нажимает. Играйте сами и смотрите окно. Esc/F10 — выход.")
    while not hk.quit:
        play_run(scr, ctl, hk, None, show=True, info="debug", act=False)


def cmd_train(args, play_only=False):
    cfg = load_config()
    scr = Screen(cfg["region"])
    hk = Hotkeys()
    ctl = Controls(cfg["region"])
    pop = Population()
    if play_only and pop.best is None:
        if os.path.exists(PRETRAINED_PATH):
            with open(PRETRAINED_PATH, encoding="utf-8") as f:
                pop.best = np.array(json.load(f)["genomes"][0])
        else:
            sys.exit("Ещё нет обученной сети: сначала python bot.py train")
    print("Переключитесь на окно игры. Старт через 3 секунды. F9 — пауза, F10 — выход.")
    time.sleep(3)
    while not hk.quit:
        if not restart(scr, ctl, hk, cfg):
            continue
        g = pop.best if play_only else pop.current()
        info = "best net" if play_only else f"gen {pop.gen} net {pop.idx + 1}/{len(pop.genomes)}"
        tr = play_run(scr, ctl, hk, g, show=not args.no_window, info=info)
        if hk.quit:
            break
        fit = tr.fitness()
        print(f"{info}: высота {tr.height_label()} px, убито {tr.kills}, бросков {tr.throws}, очки {fit:.0f}")
        if not play_only:
            pop.report(fit, tr.max_h, tr.kills)
    ctl.release()
    cv2.destroyAllWindows()


def main():
    ap = argparse.ArgumentParser(description="Нейро-бот для прыгалки в Telegram")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("setup")
    s.add_argument("--monitor", type=int, default=1, help="номер монитора (1 — основной)")
    d = sub.add_parser("debug")
    d.add_argument("--image", help="проверить распознавание на скриншоте")
    d.add_argument("--out", help="куда сохранить картинку")
    for name in ("train", "play"):
        p = sub.add_parser(name)
        p.add_argument("--no-window", action="store_true", help="не показывать окно с распознаванием")
    args = ap.parse_args()
    set_dpi_aware()
    if args.cmd == "setup":
        cmd_setup(args)
    elif args.cmd == "debug":
        cmd_debug(args)
    elif args.cmd == "train":
        cmd_train(args)
    else:
        cmd_train(args, play_only=True)


if __name__ == "__main__":
    main()
