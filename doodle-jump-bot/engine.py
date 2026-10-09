"""Ядро бота: захват экрана → распознавание → решение → нажатия.

Используется и окном (app.py), и консольным запуском (bot.py).
"""
import json
import os
import sys
import threading
import time

# На Windows с масштабированием 125%/150% координаты мыши и скриншота
# расходятся, если процесс не «DPI-aware». Включаем до импорта mss/pynput/tk.
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


def config_path():
    """Собранное приложение хранит настройки в %APPDATA%\\DoodleBot,
    запуск из исходников — рядом с кодом."""
    if getattr(sys, "frozen", False):
        base = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DoodleBot")
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, "config.json")
    return os.path.join(HERE, "config.json")


DEFAULT_CONFIG = {
    "region": None,             # {"left":..,"top":..,"width":..,"height":..} — область игры
    "key_left": "a",
    "key_right": "d",
    "throw": "space",           # "space" или "click" (клик ЛКМ по монстру)
    "restart": True,            # сам нажимать «Играть заново»
    "max_fps": 60,
    "physics": {},              # переопределение полей Physics
    "planner": {},              # deadband, fire_cooldown, fire_dx, adapt_physics, ...
}


def load_config():
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    path = config_path()
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                cfg.update(json.load(f))
        except (OSError, ValueError):
            pass
    return cfg


def save_config(cfg):
    with open(config_path(), "w", encoding="utf-8") as f:
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


def check_region(region):
    """Снимок области и разметка — для проверки, что игра выбрана верно."""
    with mss.mss() as sct:
        frame = grab(sct, region)
    sc = Detector().detect(frame)
    return frame, sc


class BotEngine:
    """Игровой цикл в отдельном потоке. Управление: start()/pause()/toggle()/stop().
    Для окна: stats (словарь с цифрами) и last_preview (кадр с разметкой)."""

    def __init__(self, cfg, log=print, want_preview=lambda: False, debug_dir=None):
        self.cfg = cfg
        self.log = log
        self.want_preview = want_preview
        self.debug_dir = debug_dir
        self.running = False
        self._quit = False
        self._thread = None
        self.last_preview = None
        self._ctl = None
        self.stats = {"fps": 0.0, "games": 0, "note": "", "player": False}

    # --- управление -----------------------------------------------------
    def start_thread(self):
        if self._thread is None or not self._thread.is_alive():
            self._quit = False
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def start(self):
        if not self.cfg.get("region"):
            self.log("Сначала выбери область игры.")
            return False
        self.start_thread()
        self.running = True
        return True

    def pause(self):
        self.running = False

    def toggle(self):
        if self.running:
            self.pause()
        else:
            self.start()
        return self.running

    def stop(self):
        self.running = False
        self._quit = True
        if self._thread is not None:
            self._thread.join(timeout=2)

    # --- цикл -----------------------------------------------------------
    def _loop(self):
        try:
            with mss.mss() as sct:
                self._run(sct)
        except Exception as e:  # чтобы ошибка не убила окно молча
            self.running = False
            self.log(f"Ошибка: {e!r}")
        finally:
            if self._ctl is not None:
                self._ctl.release_all()

    def _run(self, sct):
        was_running = False
        frames, fps_t0 = 0, time.perf_counter()
        last_restart = last_preview = last_debug = 0.0
        det = planner = ctl = phys = region = None
        while not self._quit:
            t = time.perf_counter()
            if not self.running:
                if was_running:
                    ctl.release_all()
                    was_running = False
                    self.log("⏸ Пауза")
                time.sleep(0.05)
                continue
            if not was_running:
                # Настройки могли поменяться, пока стояли на паузе.
                cfg = self.cfg
                region = cfg["region"]
                phys = Physics(**cfg.get("physics", {}))
                pcfg = dict(cfg.get("planner", {}))
                pcfg.setdefault("aim_fire", cfg.get("throw") == "click")
                planner = Planner(phys, pcfg)
                det = Detector()
                ctl = self._ctl = Controls(cfg, region)
                was_running = True
                self.log("▶ Бот играет")

            frame = grab(sct, region)
            sc = det.detect(frame, t)

            if sc.game_over is not None:
                ctl.release_all()
                if self.cfg.get("restart", True) and t - last_restart > 2.0:
                    self.stats["games"] += 1
                    self.log(f"Падение. Перезапуск (игра №{self.stats['games'] + 1})")
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

            if self.want_preview() and t - last_preview > 0.15:
                self.last_preview = draw_debug(frame, sc, plan)
                last_preview = t
            if self.debug_dir and t - last_debug > 0.5:
                os.makedirs(self.debug_dir, exist_ok=True)
                cv2.imwrite(os.path.join(self.debug_dir, f"{int(t * 1000)}.jpg"), draw_debug(frame, sc, plan))
                last_debug = t

            frames += 1
            if t - fps_t0 > 1.0:
                self.stats["fps"] = frames / (t - fps_t0)
                frames, fps_t0 = 0, t
            self.stats["note"] = plan.note if plan else "экран падения"
            self.stats["player"] = sc.player is not None

            spent = time.perf_counter() - t
            min_dt = 1.0 / self.cfg.get("max_fps", 60)
            if spent < min_dt:
                time.sleep(min_dt - spent)
