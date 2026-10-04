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
# Нейросеть: 19 входов -> 12 tanh -> 2 выхода (руль, бросок).
# Раскладка весов совпадает с pretrain/sim.js, поэтому предобученные сети подходят.
# ============================================================================
NI, NH, NO = 19, 12, 2
O_B1 = NI * NH
O_W2 = O_B1 + NH
O_B2 = O_W2 + NH * NO
NG = O_B2 + NO
# Входы, которые меняют знак при зеркальном отражении сцены (все «смещения по X»)
MIRROR = [0, 2, 4, 6, 8, 10, 12, 14]
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
class Detector:
    """Ищет на кадре платформы (широкие тёмные полоски), врагов и персонажа.
    Фон — плавный градиент, поэтому всё, что заметно темнее медианы своей строки,
    считается объектом."""

    def __init__(self, scale=0.5, top_ignore=0.09):
        self.scale = scale
        self.top_ignore = top_ignore  # верхняя полоса со счётом и значками
        self.prev_player = None

    def detect(self, bgr):
        H, W = bgr.shape[:2]
        s = self.scale
        small = cv2.resize(bgr, None, fx=s, fy=s, interpolation=cv2.INTER_AREA).astype(np.int16)
        bg = np.median(small, axis=1, keepdims=True)
        diff = np.abs(small - bg).sum(axis=2)
        darker = bg.sum(axis=2) - small.sum(axis=2)
        mask = ((diff > 60) & (darker > 30)).astype(np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        n, lab, st, _ = cv2.connectedComponentsWithStats(mask)

        plats, blobs = [], []
        min_area = (0.012 * W * s) ** 2
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if a < min_area:
                continue
            fx, fy, fw, fh = x / s, y / s, w / s, h / s
            cy = fy + fh / 2
            if cy < self.top_ignore * H:
                continue
            fill = a / float(w * h)
            comp = lab[y:y + h, x:x + w] == i
            # Облака внизу экрана — тонкие светлые контуры, у настоящих объектов контраст заметно сильнее
            if darker[y:y + h, x:x + w][comp].mean() < 150:
                continue
            if 0.08 * W <= fw <= 0.25 * W and fw / max(fh, 1) > 3.2 and fill > 0.55:
                plats.append({"x": fx + fw / 2, "y": fy, "w": fw})
                continue
            if 0.05 * W <= fw <= 0.25 * W and 0.05 * W <= fh <= 0.25 * W and 0.45 < fw / fh < 2.2 and fill > 0.35:
                px = small[y:y + h, x:x + w][comp]
                b, g_, r = px[:, 0], px[:, 1], px[:, 2]
                pink = float(np.mean((r - b > 25) & (r - g_ > 35) & (b >= g_ - 15)))
                blobs.append({"x": fx + fw / 2, "y": cy, "w": fw, "h": fh, "pink": pink})

        player = self._pick_player(blobs, W, H)
        enemies = [b for b in blobs if b is not player]
        if player is not None:
            self.prev_player = (player["x"], player["y"])
        return {"W": W, "H": H, "plats": plats, "player": player, "enemies": enemies}

    def _pick_player(self, blobs, W, H):
        best, best_score = None, -1e9
        for b in blobs:
            if b["pink"] > 0.25:  # розовые — свиньи
                continue
            score = -b["pink"] * 4
            if self.prev_player:
                d = np.hypot(wdx(self.prev_player[0], b["x"], W), self.prev_player[1] - b["y"])
                score -= d / (0.15 * H)
            else:
                score += b["y"] / H  # в начале игры персонаж обычно внизу
            if score > best_score:
                best, best_score = b, score
        return best

    def forget(self):
        self.prev_player = None


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
SIM_APEX = 196.0      # высота прыжка в симуляторе, px
SIM_PERIOD = 70.0     # длительность прыжка в симуляторе, тики
SIM_W = 400.0
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
        self.apex = 0.25 * H     # оценки высоты и длительности прыжка уточняются по ходу игры
        self.period = 1.0
        self.bounces = []
        self.rises = []
        self.min_wy_since_bounce = None
        self.last_throw = -9.0
        self.throws = 0
        self.kills = 0
        self.prev_enemies = []
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
        self.scroll += self._scroll_delta(det["plats"])
        self.prev_plats = det["plats"]
        dt = (t - self.prev_t) if self.prev_t else 1 / 30
        dt = max(dt, 1e-3)
        self.prev_t = t

        # Убийства: враг пропал не у нижнего края вскоре после броска
        if t - self.last_throw < 1.5 and len(det["enemies"]) < len(self.prev_enemies):
            gone = [e for e in self.prev_enemies
                    if not any(abs(wdx(e["x"], f["x"], W)) < 0.1 * W and abs(e["y"] - f["y"]) < 0.1 * H
                               for f in det["enemies"])]
            self.kills += sum(1 for e in gone if e["y"] < 0.85 * H)
        self.prev_enemies = det["enemies"]

        p = det["player"]
        if p is None:
            return
        self.last_seen = t
        wy = p["y"] - self.scroll
        if self.prev_p is not None:
            vx = wdx(self.prev_p[0], p["x"], W) / dt
            vy = (wy - self.prev_p[1]) / dt
            self.vx = 0.5 * self.vx + 0.5 * vx
            prev_vy = self.vy
            self.vy = 0.5 * self.vy + 0.5 * vy
            # Отскок: падали — и резко полетели вверх
            if prev_vy > 0.15 * H and self.vy < -0.15 * H:
                self._on_bounce(det, p, wy, t)
        self.prev_p = (p["x"], wy)
        if self.start_wy is None:
            self.start_wy = wy
            self.base = (p["x"], wy + p["h"] / 2)
        self.max_h = max(self.max_h, self.start_wy - wy)
        if self.min_wy_since_bounce is None or wy < self.min_wy_since_bounce:
            self.min_wy_since_bounce = wy

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
            if 0.05 * self.H < rise < 0.9 * self.H:
                self.rises = (self.rises + [rise])[-12:]
                self.apex = float(np.median(self.rises))
        if self.bounces:
            per = t - self.bounces[-1]
            if 0.3 < per < 4:
                self.period = float(np.median(([per] + [b - a for a, b in zip(self.bounces, self.bounces[1:])])[-12:]))
        self.bounces = (self.bounces + [t])[-13:]
        self.base = (best[1]["x"] if best else p["x"], base_y)
        self.min_wy_since_bounce = wy

    def inputs(self, det, t):
        """19 входов в тех же единицах, что и в симуляторе."""
        W, H = self.W, self.H
        p = det["player"]
        kv = SIM_APEX / self.apex              # реальные px по вертикали -> px симулятора
        tick = self.period / SIM_PERIOD        # секунд в одном тике симулятора
        vx_sim = self.vx * (SIM_W / W) * tick
        vy_sim = self.vy * kv * tick
        inp = [vx_sim / 6.2, vy_sim / 15.0]
        feet = p["y"] + p["h"] / 2
        base_wy = self.base[1] if self.base else feet - self.scroll
        nxt = [pl for pl in det["plats"] if pl["y"] - self.scroll < base_wy - 0.01 * H]
        nxt.sort(key=lambda pl: -pl["y"])
        for i in range(3):
            if i < len(nxt):
                pl = nxt[i]
                inp += [wdx(p["x"], pl["x"], W) / (W / 2), (pl["y"] - feet) * kv / 300.0, 0.0, 1.0]
            else:
                inp += [0.0, 0.0, 0.0, 0.0]
        enemy = self.nearest_enemy(det)
        if enemy:
            inp += [wdx(p["x"], enemy["x"], W) / (W / 2), (enemy["y"] - p["y"]) * kv / 300.0, 1.0]
        else:
            inp += [0.0, 0.0, 0.0]
        inp += [1.0 if t - self.last_throw > COOLDOWN_S else 0.0, 1.0]
        return np.array(inp, dtype=np.float64), nxt[:3], enemy

    def nearest_enemy(self, det):
        p = det["player"]
        best, bd = None, 1e9
        for e in det["enemies"]:
            d = np.hypot(wdx(p["x"], e["x"], self.W), e["y"] - p["y"])
            if d < bd:
                best, bd = e, d
        return best

    def fitness(self):
        return self.max_h * SIM_APEX / self.apex + 250 * self.kills - 3 * self.throws

    def height_label(self):
        return int(self.max_h)


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
        if self.dry or d == self.held:
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
        if os.path.exists(STATE_PATH):
            with open(STATE_PATH, encoding="utf-8") as f:
                s = json.load(f)
            if s.get("ng") == NG:
                self.gen, self.idx, self.history = s["gen"], s.get("idx", 0), s.get("history", [])
                self.best_fit = s.get("best_fit", -1e9)
                self.best = np.array(s["best"]) if s.get("best") else None
                self.genomes = [np.array(g) for g in s["genomes"]]
                self.fits = s.get("fits", [])
                print(f"Продолжаю обучение: поколение {self.gen}, сеть {self.idx + 1}")
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
            self.genomes = seeds[:self.SIZE]
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
        data = {"ng": NG, "gen": self.gen, "idx": self.idx, "history": self.history,
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
        move, throw, nxt, enemy = 0, False, [], None
        if det["player"] is not None:
            inp, nxt, enemy = tr.inputs(det, t)
            if genome is not None:
                move, throw, _ = decide(genome, inp)
            if act:
                ctl.move(move)
                if throw and enemy and t - tr.last_throw > COOLDOWN_S:
                    ctl.click(enemy["x"], enemy["y"])
                    tr.last_throw = t
                    tr.throws += 1
        else:
            ctl.release()
        frames += 1
        if on_frame is not None and frames % 2 == 0:
            fps = frames / max(t - t_start, 1e-3)
            on_frame(draw_debug(img, det, tr, nxt, enemy, move, throw, f"{info} {fps:.0f} fps"), tr)
        elif show:
            fps = frames / max(t - t_start, 1e-3)
            cv2.imshow(DEBUG_WINDOW, draw_debug(img, det, tr, nxt, enemy, move, throw, f"{info} {fps:.0f} fps"))
            if cv2.waitKey(1) & 0xFF == 27:
                hk.quit = True
        # Смерть: персонаж пропал или улетел за нижний край
        p = det["player"]
        if t - tr.last_seen > 0.8 and t - t_start > 2:
            break
        if p is not None and p["y"] + p["h"] / 2 > 0.98 * region["height"] and tr.vy > 0:
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
