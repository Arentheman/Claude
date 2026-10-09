"""Бот для Doodle Jump в Telegram mini-app.

  python bot.py --calibrate   — указать, где на экране игра (один раз)
  python bot.py               — запуск. F8 — старт/пауза, F10 — выход.
  python bot.py --show        — то же + окно с тем, что «видит» бот
"""
import argparse
import json
import os
import sys
import time

# На Windows с масштабированием 125%/150% координаты мыши и скриншота
# расходятся, если процесс не «DPI-aware». Включаем до импорта mss/pynput.
if sys.platform == "win32":
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import cv2
import mss
import numpy as np
from pynput import keyboard, mouse

from planner import Physics, Planner
from vision import CANON_W, Detector, draw_debug

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "config.json")

DEFAULT_CONFIG = {
    "region": None,             # {"left":..,"top":..,"width":..,"height":..} — область игры
    "key_left": "a",
    "key_right": "d",
    "throw": "space",           # "space" или "click" (клик ЛКМ по монстру)
    "restart": True,            # сам нажимать «Играть заново»
    "max_fps": 60,
    "physics": {},              # переопределение полей Physics
    "planner": {},              # deadband, fire_cooldown, fire_dx, adapt_physics
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def key_of(name):
    """Клавиша по имени. На Windows — по виртуальному коду, чтобы работало
    и при русской раскладке (иначе «a» отправится как юникод-символ)."""
    special = {"space": keyboard.Key.space, "left": keyboard.Key.left, "right": keyboard.Key.right}
    if name in special:
        return special[name]
    if sys.platform == "win32" and len(name) == 1 and name.isalnum():
        return keyboard.KeyCode.from_vk(ord(name.upper()))
    return keyboard.KeyCode.from_char(name)


def grab(sct, region):
    img = np.asarray(sct.grab(region))
    return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)


# ----------------------------------------------------------------------
def calibrate(cfg):
    print("Калибровка области игры.")
    print("1) Наведи курсор на ЛЕВЫЙ ВЕРХНИЙ угол игрового поля и нажми F7.")
    print("2) Наведи курсор на ПРАВЫЙ НИЖНИЙ угол игрового поля и нажми F7.")
    print("   (бери только саму игру, без заголовка окна Telegram)")
    pts = []
    m = mouse.Controller()

    def on_press(k):
        if k == keyboard.Key.f7:
            pts.append(tuple(int(v) for v in m.position))
            print(f"   точка {len(pts)}: {pts[-1]}")
            if len(pts) == 2:
                return False
        elif k == keyboard.Key.esc:
            return False

    with keyboard.Listener(on_press=on_press) as lst:
        lst.join()
    if len(pts) < 2:
        print("Отменено.")
        return
    (x0, y0), (x1, y1) = pts
    region = {"left": min(x0, x1), "top": min(y0, y1),
              "width": abs(x1 - x0), "height": abs(y1 - y0)}
    cfg["region"] = region
    save_config(cfg)
    print("Сохранено в config.json:", region)

    with mss.mss() as sct:
        frame = grab(sct, region)
    det = Detector()
    sc = det.detect(frame)
    out = os.path.join(HERE, "calibration_check.png")
    cv2.imwrite(out, draw_debug(frame, sc))
    print(f"Проверка: платформ {len(sc.platforms)}, герой {'найден' if sc.player else 'НЕ найден'}, "
          f"монстров {len(sc.monsters)}, дыр {len(sc.holes)}")
    print(f"Картинка с разметкой: {out}")
    if not sc.platforms:
        print("Платформ не видно — проверь, что область выбрана верно и игра запущена.")


# ----------------------------------------------------------------------
class Controls:
    def __init__(self, cfg, region):
        self.kb = keyboard.Controller()
        self.ms = mouse.Controller()
        self.left = key_of(cfg["key_left"])
        self.right = key_of(cfg["key_right"])
        self.throw = cfg["throw"]
        self.region = region
        self.scale = region["width"] / CANON_W
        self.held = None

    def to_screen(self, x, y):
        return (int(round(self.region["left"] + float(x) * self.scale)),
                int(round(self.region["top"] + float(y) * self.scale)))

    def move(self, direction):
        if direction == self.held:
            return
        if self.held == "left":
            self.kb.release(self.left)
        elif self.held == "right":
            self.kb.release(self.right)
        if direction == "left":
            self.kb.press(self.left)
        elif direction == "right":
            self.kb.press(self.right)
        self.held = direction

    def fire(self, at=None):
        if self.throw == "click" and at is not None:
            self.ms.position = self.to_screen(*at)
            self.ms.click(mouse.Button.left)
        else:
            self.kb.press(keyboard.Key.space)
            self.kb.release(keyboard.Key.space)

    def click(self, x, y):
        self.release_all()
        self.ms.position = self.to_screen(x, y)
        time.sleep(0.05)
        self.ms.click(mouse.Button.left)

    def release_all(self):
        self.move(None)


def run(cfg, show=False, save_debug=False):
    region = cfg.get("region")
    if not region:
        print("Сначала откалибруй область игры: python bot.py --calibrate")
        return
    phys = Physics(**cfg.get("physics", {}))
    pcfg = dict(cfg.get("planner", {}))
    pcfg.setdefault("aim_fire", cfg.get("throw") == "click")
    planner = Planner(phys, pcfg)
    det = Detector()
    ctl = Controls(cfg, region)

    state = {"running": False, "quit": False}

    def on_press(k):
        if k == keyboard.Key.f8:
            state["running"] = not state["running"]
            print("▶ Старт" if state["running"] else "⏸ Пауза")
        elif k == keyboard.Key.f10:
            state["quit"] = True
            return False

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("Готово. Открой игру, кликни по ней (чтобы окно было активным) и нажми F8.")
    print("F8 — старт/пауза, F10 — выход.")

    debug_dir = os.path.join(HERE, "debug")
    if save_debug:
        os.makedirs(debug_dir, exist_ok=True)

    min_dt = 1.0 / cfg.get("max_fps", 60)
    frames, fps_t0 = 0, time.perf_counter()
    last_restart = 0.0
    last_debug = 0.0
    was_running = False
    try:
        with mss.mss() as sct:
            while not state["quit"]:
                t = time.perf_counter()
                if not state["running"]:
                    if was_running:
                        ctl.release_all()
                        was_running = False
                    time.sleep(0.05)
                    continue
                if not was_running:
                    det.reset()
                    planner.reset()
                    was_running = True

                frame = grab(sct, region)
                sc = det.detect(frame, t)

                if sc.game_over is not None:
                    ctl.release_all()
                    if cfg.get("restart", True) and t - last_restart > 2.0:
                        print(f"Падение. Перезапуск... (прыжок {phys.jump_speed:.0f}, бег {phys.run_speed:.0f})")
                        time.sleep(0.8)
                        ctl.click(*sc.game_over)
                        last_restart = time.perf_counter()
                        det.reset()
                        planner.reset()
                    plan = None
                else:
                    plan = planner.step(sc, t)
                    if planner.lost_frames > 30:
                        planner.reset()
                    ctl.move(plan.move)
                    if plan.fire:
                        ctl.fire(plan.fire_at)

                if show or (save_debug and t - last_debug > 0.5):
                    dbg = draw_debug(frame, sc, plan)
                    if show:
                        cv2.imshow("doodle bot", cv2.resize(dbg, None, fx=0.6, fy=0.6))
                        cv2.waitKey(1)
                    if save_debug and t - last_debug > 0.5:
                        cv2.imwrite(os.path.join(debug_dir, f"{int(t * 1000)}.jpg"), dbg)
                        last_debug = t

                frames += 1
                if t - fps_t0 > 5:
                    print(f"{frames / (t - fps_t0):.0f} к/с; {plan.note if plan else ''}")
                    frames, fps_t0 = 0, t
                spent = time.perf_counter() - t
                if spent < min_dt:
                    time.sleep(min_dt - spent)

    except KeyboardInterrupt:
        pass
    finally:
        # Никогда не оставляем A/D зажатыми.
        ctl.release_all()
        listener.stop()
    print("Выход.")


def main():
    ap = argparse.ArgumentParser(description="Бот для Doodle Jump (Telegram mini-app)")
    ap.add_argument("--calibrate", action="store_true", help="выбрать область игры на экране")
    ap.add_argument("--show", action="store_true", help="показывать окно с разметкой")
    ap.add_argument("--debug", action="store_true", help="сохранять кадры с разметкой в папку debug/")
    args = ap.parse_args()
    cfg = load_config()
    if args.calibrate:
        calibrate(cfg)
    else:
        run(cfg, show=args.show, save_debug=args.debug)


if __name__ == "__main__":
    main()
