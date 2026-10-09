"""Распознавание объектов игры на кадре.

Все координаты — в «каноническом» пространстве: кадр игры масштабируется
до ширины CANON_W (как на записи экрана, 488 px), поэтому пороги не зависят
от реального размера окна Telegram.
"""
import os
import sys
from dataclasses import dataclass, field

import cv2
import numpy as np

CANON_W = 488
# Внутренняя обработка идёт на кадре в 2 раза меньше (быстрее).
SCALE = 2

# Пороговые значения (HSV в OpenCV: H 0..179, S/V 0..255).
FG_DIFF = 40                    # насколько пиксель отличается от «размытого фона»
PLATFORM_H = (8, 52)            # трава/дерево платформ
PLATFORM_S = (20, 210)
PLATFORM_V = (40, 205)
HOLE_H = (122, 158)             # фиолетовая чёрная дыра
PIG_H_LO, PIG_H_HI = 158, 6     # розовая свинья (оттенок через 0)
GHOST_H = (86, 99)              # голубой призрак (небо чуть «синее»: H≈102-104)
SKIN_H_LO, SKIN_H_HI = 160, 22  # кожа героя


@dataclass
class Platform:
    x: float          # центр
    y: float          # верхняя кромка
    w: float
    broken: bool = False
    bonus: bool = False   # на платформе стоит пружина / ракета / буст
    vx: float = 0.0       # скорость, px/с (если платформа движется)


@dataclass
class Blob:
    x: float
    y: float          # центр
    w: float
    h: float


@dataclass
class Scene:
    width: int
    height: int
    player: Blob | None = None
    platforms: list = field(default_factory=list)
    monsters: list = field(default_factory=list)   # свиньи и призраки
    holes: list = field(default_factory=list)      # чёрные дыры
    bonuses: list = field(default_factory=list)
    scroll: float = 0.0      # на сколько px мир сдвинулся вниз с прошлого кадра
    game_over: tuple | None = None   # центр кнопки «Играть заново», если видна


def _hue_mask(h, lo, hi):
    if lo <= hi:
        return (h >= lo) & (h <= hi)
    return (h >= lo) | (h <= hi)


def _components(mask, min_area):
    n, _, stats, cents = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a >= min_area:
            out.append((x, y, w, h, a))
    return out


def to_canon(frame_bgr):
    h, w = frame_bgr.shape[:2]
    if w == CANON_W:
        return frame_bgr
    nh = int(round(h * CANON_W / w))
    return cv2.resize(frame_bgr, (CANON_W, nh), interpolation=cv2.INTER_AREA)


# В собранном .exe данные лежат во временной папке распаковки (sys._MEIPASS).
TEMPLATE_DIR = os.path.join(getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__))), "templates")
PLAYER_MATCH_MIN = 0.5
MASK_ERODE = 9


def imwrite_any(path, img):
    """cv2.imwrite, который работает и с путями на кириллице (Windows)."""
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".png", img)
    if ok:
        buf.tofile(path)
    return ok


def load_player_templates(scale=SCALE):
    """Шаблоны героя (позы «падает» и «прыгает») + зеркальные копии."""
    out = []
    for name in sorted(os.listdir(TEMPLATE_DIR)):
        if not name.startswith("player_"):
            continue
        # Не cv2.imread: на Windows он не открывает пути с кириллицей
        # (например, C:\Users\Имя\...) и молча возвращает None.
        path = os.path.join(TEMPLATE_DIR, name)
        rgba = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_UNCHANGED)
        if rgba is None or rgba.ndim != 3 or rgba.shape[2] != 4:
            raise RuntimeError(f"не удалось прочитать шаблон героя: {path}")
        g = cv2.cvtColor(rgba[..., :3], cv2.COLOR_BGR2GRAY)
        # Маску сжимаем: по краю спрайта в шаблон попала кайма дневного фона,
        # из-за которой ночью (на тёмном фоне) герой переставал узнаваться.
        m = cv2.erode(rgba[..., 3], np.ones((MASK_ERODE, MASK_ERODE), np.uint8))
        size = (g.shape[1] // scale, g.shape[0] // scale)
        g = cv2.resize(g, size, interpolation=cv2.INTER_AREA)
        m = (cv2.resize(m, size, interpolation=cv2.INTER_AREA) > 127).astype(np.uint8) * 255
        out.append((g, m))
        out.append((cv2.flip(g, 1), cv2.flip(m, 1)))
    return out


class Detector:
    def __init__(self, hud_box=(195, 55, 290, 105)):
        # Плашка с метрами вверху по центру — её игнорируем.
        self.hud_box = hud_box
        self.prev_platforms = []
        self.prev_player = None
        self.templates = load_player_templates()
        self.player_score = 0.0
        self.prev_t = None
        self.debug_cands = []

    def _match_player(self, gray, W):
        """Поиск героя шаблонами. Кадр дополняется по краям «заворотом»,
        чтобы находить героя, наполовину ушедшего за границу экрана.
        Если герой был найден в прошлом кадре — ищем только рядом (быстрее)."""
        pad = 14
        g = cv2.copyMakeBorder(gray, 0, 0, pad, pad, cv2.BORDER_WRAP)
        s = SCALE
        x0, y0 = 0, 0
        prev = self.prev_player
        if prev is not None and self.player_score >= 0.6:
            cx, cy = prev.x / s + pad, prev.y / s
            rx, ry = 70, 100
            x0, x1 = max(0, int(cx - rx)), min(g.shape[1], int(cx + rx))
            y0, y1 = max(0, int(cy - ry)), min(g.shape[0], int(cy + ry))
            if x1 - x0 > 40 and y1 - y0 > 40:
                g = g[y0:y1, x0:x1]
            else:
                x0, y0 = 0, 0
        best = (-1.0, None, None)
        for t, m in self.templates:
            if g.shape[0] < t.shape[0] or g.shape[1] < t.shape[1]:
                continue
            r = cv2.matchTemplate(g, t, cv2.TM_CCOEFF_NORMED, mask=m)
            r = np.nan_to_num(r, nan=-1.0, posinf=-1.0, neginf=-1.0)
            _, mv, _, ml = cv2.minMaxLoc(r)
            if mv > best[0]:
                best = (mv, ml, t.shape)
        mv, ml, shp = best
        if ml is None or mv < PLAYER_MATCH_MIN:
            if x0 or y0 or g.shape[0] < gray.shape[0]:
                # В окне не нашли — повторяем по всему кадру.
                self.player_score = 0.0
                return self._match_player(gray, W)
            return None, mv
        cx = ((ml[0] + x0 - pad + shp[1] / 2) * s) % W
        cy = (ml[1] + y0 + shp[0] / 2) * s
        return Blob(cx, cy, 40.0, 48.0), mv

    def reset(self):
        self.prev_platforms = []
        self.prev_player = None
        self.player_score = 0.0
        self.prev_t = None

    def detect(self, frame_bgr, t=None) -> Scene:
        """t — время кадра в секундах (для скоростей). Без t считаем 30 к/с."""
        img = to_canon(frame_bgr)
        H, W = img.shape[:2]
        s = SCALE
        sm = cv2.resize(img, (W // s, H // s), interpolation=cv2.INTER_AREA)
        hsv = cv2.cvtColor(sm, cv2.COLOR_BGR2HSV)
        hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]

        prev_t = self.prev_t
        if t is None:
            t = (prev_t or 0.0) + 1 / 30
        dt = max(1e-3, t - prev_t) if prev_t is not None else 1 / 30
        self.prev_t = t

        go = detect_game_over(hsv)
        if go is not None:
            scene = Scene(W, H, game_over=(go[0] * s, go[1] * s))
            self.prev_platforms, self.prev_player = [], None
            return scene

        # Фон плавный (градиент, облака) — медиана большого окна его повторяет,
        # а мелкие объекты (платформы, персонажи) из неё выпадают.
        q = cv2.resize(sm, (sm.shape[1] // 2, sm.shape[0] // 2), interpolation=cv2.INTER_AREA)
        bg = cv2.resize(cv2.medianBlur(q, 15), (sm.shape[1], sm.shape[0]), interpolation=cv2.INTER_LINEAR)
        fg = cv2.absdiff(sm, bg).max(axis=2) > FG_DIFF

        hx0, hy0, hx1, hy1 = (v // s for v in self.hud_box)
        fg[hy0:hy1, hx0:hx1] = False

        scene = Scene(W, H)

        # --- Чёрные дыры -------------------------------------------------
        hole = _hue_mask(hh, *HOLE_H) & (ss > 90) & (vv > 35)
        hole = cv2.morphologyEx(hole.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        for x, y, w, h, a in _components(hole, 60):
            scene.holes.append(Blob((x + w / 2) * s, (y + h / 2) * s, w * s, h * s))

        # --- Платформы ---------------------------------------------------
        pc = (_hue_mask(hh, *PLATFORM_H) & (ss >= PLATFORM_S[0]) & (ss <= PLATFORM_S[1])
              & (vv >= PLATFORM_V[0]) & (vv <= PLATFORM_V[1]) & fg).astype(np.uint8)
        pc = cv2.morphologyEx(pc, cv2.MORPH_CLOSE, np.ones((3, 5), np.uint8))
        pc = cv2.morphologyEx(pc, cv2.MORPH_OPEN, np.ones((2, 11), np.uint8))
        plat_mask = np.zeros_like(pc)
        for x, y, w, h, a in _components(pc, 25):
            if not (18 <= w <= 42 and 2 <= h <= 10):
                continue
            region = hsv[y:y + h, x:x + w]
            mean_h = float(np.median(region[..., 0]))
            mean_s = float(np.median(region[..., 1]))
            broken = mean_h < 26 and mean_s > 70
            scene.platforms.append(Platform((x + w / 2) * s, y * s, w * s, broken=broken))
            plat_mask[max(0, y - 1):y + h + 2, max(0, x - 1):x + w + 1] = 1

        # --- Монстры -----------------------------------------------------
        pig_raw = _hue_mask(hh, PIG_H_LO, PIG_H_HI) & (ss > 75) & (vv > 90) & fg
        pig = cv2.morphologyEx(pig_raw.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        for x, y, w, h, a in _components(pig, 70):
            # У героя тоже есть розовые пятна, но у свиньи их в разы больше.
            if w >= 14 and h >= 10 and pig_raw[y:y + h, x:x + w].sum() >= 110:
                scene.monsters.append(Blob((x + w / 2) * s, (y + h / 2) * s, w * s, h * s))

        ghost = _hue_mask(hh, *GHOST_H) & (ss > 50) & (vv > 200)
        ghost &= cv2.dilate(fg.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
        ghost = cv2.morphologyEx(ghost.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        for x, y, w, h, a in _components(ghost, 110):
            if 14 <= w <= 40 and 14 <= h <= 40 and a > 0.5 * w * h:
                scene.monsters.append(Blob((x + w / 2) * s, (y + h / 2) * s, w * s, h * s))

        # --- Остальные объекты: герой и бонусы -----------------------------
        rest = fg & (plat_mask == 0)
        for m in scene.monsters + scene.holes:
            x0, y0 = int((m.x - m.w / 2) / s) - 2, int((m.y - m.h / 2) / s) - 2
            rest[max(0, y0):y0 + int(m.h / s) + 4, max(0, x0):x0 + int(m.w / s) + 4] = False
        rest = cv2.morphologyEx(rest.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
        skin = _hue_mask(hh, SKIN_H_LO, SKIN_H_HI) & (ss > 25) & (ss < 150) & (vv > 70) & (vv < 235)

        cands = []
        for x, y, w, h, a in _components(rest, 25):
            if w < 5 or h < 6:
                continue
            sk = float(skin[y:y + h, x:x + w].mean())
            sat = float(ss[y:y + h, x:x + w].mean())
            cands.append(((x + w / 2) * s, (y + h / 2) * s, w * s, h * s, a, sk, sat))
        self.debug_cands = cands

        # Герой: объект нужного размера с «кожей» и насыщенными цветами.
        # Пружины/ракеты тоже коричневатые, но они мельче или бледнее.
        best, best_score = None, 0.0
        for c in cands:
            cx, cy, w, h, a, sk, sat = c
            if not (150 <= a <= 520 and 24 <= h <= 64 and w <= 58):
                continue
            score = a * (sk + 0.05) * sat
            if self.prev_player is not None:
                dx = abs(cx - self.prev_player.x)
                dx = min(dx, W - dx)            # с учётом прохода сквозь край
                d = dx + abs(cy - self.prev_player.y)
                score *= 1.0 / (1.0 + d / 400.0)
            if score > best_score:
                best, best_score = c, score
        tp, self.player_score = self._match_player(cv2.cvtColor(sm, cv2.COLOR_BGR2GRAY), W)
        if tp is not None:
            scene.player = tp
            # Кандидат-«пятно» на месте героя — это он, а не бонус.
            for c in cands:
                if abs(c[0] - tp.x) < 20 and abs(c[1] - tp.y) < 24:
                    best = c
            # Героя (особенно в «пузыре») детектор свиней иногда принимает
            # за монстра — убираем «монстров», стоящих ровно на герое.
            if self.player_score >= 0.6:
                scene.monsters = [m for m in scene.monsters
                                  if not (abs(m.x - tp.x) < m.w / 2 and abs(m.y - tp.y) < m.h / 2)]
        elif best is not None and self.prev_player is not None:
            # Запасной вариант по цветным пятнам — только рядом с тем местом,
            # где герой был только что: иначе ночью за героя принимался призрак.
            dx = abs(best[0] - self.prev_player.x)
            dx = min(dx, W - dx)
            if dx < 60 and abs(best[1] - self.prev_player.y) < 90:
                scene.player = Blob(best[0], best[1], best[2], best[3])
        self.prev_player = scene.player

        # Бонусы: объекты, стоящие прямо на платформе (пружины, ракеты, бусты).
        for c in cands:
            if c is best:
                continue
            cx, cy, w, h, a, sk, sat = c
            if a < 30 or h < 14:
                continue
            bottom = cy + h / 2
            for p in scene.platforms:
                if abs(cx - p.x) < p.w / 2 and -6 <= p.y - bottom <= 14:
                    p.bonus = True
                    scene.bonuses.append(Blob(cx, cy, w, h))
                    break

        self._track_platforms(scene, dt)
        return scene

    def _track_platforms(self, scene, dt):
        """Оценка скорости движущихся платформ с учётом вертикальной прокрутки экрана."""
        prev = self.prev_platforms
        if prev and scene.platforms:
            # Прокрутка: самый частый сдвиг по y между парами платформ с одинаковым x.
            dys = [p.y - q.y for p in scene.platforms for q in prev
                   if abs(p.x - q.x) < 6 and -60 < p.y - q.y < 120]
            scroll = float(np.median(dys)) if dys else 0.0
            scene.scroll = scroll
            for p in scene.platforms:
                best = None
                for q in prev:
                    dy = abs(p.y - q.y - scroll)
                    dx = abs(p.x - q.x)
                    if dy < 8 and dx < 25:
                        d = dy * 3 + dx
                        if best is None or d < best[0]:
                            best = (d, q)
                if best is not None:
                    q = best[1]
                    v = (p.x - q.x) / dt
                    p.vx = 0.5 * q.vx + 0.5 * v if abs(v) < 400 else q.vx
        self.prev_platforms = scene.platforms


def detect_game_over(hsv):
    """Экран «Падение»: тёмный фон и большая красная кнопка «Играть заново».
    Возвращает центр кнопки (в координатах уменьшенного кадра) или None."""
    hh, ss, vv = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    if float((vv < 110).mean()) < 0.45:
        return None
    red = (_hue_mask(hh, 170, 8) & (ss > 130) & (vv > 120)).astype(np.uint8)
    W = hsv.shape[1]
    best = None
    for x, y, w, h, a in _components(red, 200):
        if w > 0.4 * W and 8 <= h <= 40 and a > 0.6 * w * h:
            if best is None or y < best[1]:
                best = (x + w / 2, y + h / 2)
    return best


def draw_debug(frame_bgr, scene: Scene, plan=None):
    img = to_canon(frame_bgr).copy()
    for p in scene.platforms:
        col = (0, 0, 255) if p.broken else ((0, 215, 255) if p.bonus else (0, 255, 0))
        cv2.rectangle(img, (int(p.x - p.w / 2), int(p.y)), (int(p.x + p.w / 2), int(p.y + 10)), col, 2)
        if abs(p.vx) > 25:
            cv2.arrowedLine(img, (int(p.x), int(p.y) + 5), (int(p.x + p.vx * 0.3), int(p.y) + 5), (255, 0, 255), 2)
    for m in scene.monsters:
        cv2.rectangle(img, (int(m.x - m.w / 2), int(m.y - m.h / 2)), (int(m.x + m.w / 2), int(m.y + m.h / 2)), (0, 0, 255), 2)
    for o in scene.holes:
        cv2.circle(img, (int(o.x), int(o.y)), int(max(o.w, o.h) / 2), (255, 0, 128), 2)
    for b in scene.bonuses:
        cv2.rectangle(img, (int(b.x - b.w / 2), int(b.y - b.h / 2)), (int(b.x + b.w / 2), int(b.y + b.h / 2)), (0, 215, 255), 1)
    if scene.player:
        pl = scene.player
        cv2.rectangle(img, (int(pl.x - pl.w / 2), int(pl.y - pl.h / 2)), (int(pl.x + pl.w / 2), int(pl.y + pl.h / 2)), (255, 128, 0), 2)
    if scene.game_over:
        cv2.circle(img, (int(scene.game_over[0]), int(scene.game_over[1])), 20, (0, 255, 255), 3)
    if plan is not None:
        if plan.target is not None and scene.player is not None:
            tx, ty = plan.target
            cv2.line(img, (int(scene.player.x), int(scene.player.y)), (int(tx), int(ty)), (255, 255, 0), 2)
            cv2.circle(img, (int(tx), int(ty)), 7, (255, 255, 0), -1)
        txt = f"{plan.move or '-'} {'FIRE ' if plan.fire else ''}{plan.note}"
        cv2.putText(img, txt, (8, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3)
        cv2.putText(img, txt, (8, img.shape[0] - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
    return img
