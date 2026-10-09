"""Окно бота для Doodle Jump (Telegram mini-app). Из него собирается DoodleBot.exe."""
import queue
import sys
import time
import tkinter as tk
from tkinter import ttk

import engine  # первым: включает DPI-awareness до создания окна
import cv2
import mss
from PIL import Image, ImageEnhance, ImageTk
from pynput import keyboard

from vision import draw_debug

PREVIEW_H = 470
APP_TITLE = "Doodle Jump бот"


class RegionPicker:
    """Полупрозрачный снимок всего экрана: игрок обводит игру мышкой."""

    def __init__(self, root, on_done):
        self.on_done = on_done
        with mss.mss() as sct:
            mon = sct.monitors[0]            # весь рабочий стол (все мониторы)
            shot = sct.grab(mon)
        self.left, self.top = mon["left"], mon["top"]
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        img = ImageEnhance.Brightness(img).enhance(0.55)
        self.photo = ImageTk.PhotoImage(img)

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")
        self.win.attributes("-topmost", True)
        self.cv = tk.Canvas(self.win, highlightthickness=0, cursor="crosshair")
        self.cv.pack(fill="both", expand=True)
        self.cv.create_image(0, 0, image=self.photo, anchor="nw")
        self.cv.create_text(
            mon["width"] // 2, 40, fill="white", font=("Segoe UI", 18, "bold"),
            text="Обведи мышкой игровое поле (без заголовка окна Telegram).  Esc — отмена")
        self.rect = None
        self.start = None
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.win.bind("<Escape>", lambda e: self._finish(None))
        self.win.focus_force()

    def _press(self, e):
        self.start = (e.x, e.y)
        if self.rect:
            self.cv.delete(self.rect)
        self.rect = self.cv.create_rectangle(e.x, e.y, e.x, e.y, outline="#3ddc84", width=3)

    def _drag(self, e):
        if self.start:
            self.cv.coords(self.rect, self.start[0], self.start[1], e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        x1, y1 = e.x, e.y
        if abs(x1 - x0) < 60 or abs(y1 - y0) < 100:
            return                                  # случайный клик — ждём нормальную рамку
        self._finish({"left": self.left + min(x0, x1), "top": self.top + min(y0, y1),
                      "width": abs(x1 - x0), "height": abs(y1 - y0)})

    def _finish(self, region):
        self.win.destroy()
        self.on_done(region)


class App:
    def __init__(self):
        self.cfg = engine.load_config()
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.resizable(False, False)
        self.logq = queue.Queue()
        self.show_preview = tk.BooleanVar(value=True)
        self.engine = engine.BotEngine(self.cfg, log=self.logq.put,
                                       want_preview=self.show_preview.get)
        self.preview_img = None
        self._build()
        self._update_region_label()
        self._start_hotkeys()
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.after(150, self._tick)

    # --- интерфейс ------------------------------------------------------
    def _build(self):
        pad = {"padx": 10, "pady": 4}
        left = ttk.Frame(self.root)
        left.grid(row=0, column=0, sticky="n", padx=6, pady=6)

        ttk.Label(left, text=APP_TITLE, font=("Segoe UI", 14, "bold")).pack(anchor="w", **pad)

        f1 = ttk.LabelFrame(left, text="1. Где игра")
        f1.pack(fill="x", **pad)
        ttk.Button(f1, text="Выбрать область игры…", command=self._pick_region).pack(fill="x", padx=8, pady=6)
        self.region_lbl = ttk.Label(f1, text="", wraplength=260)
        self.region_lbl.pack(anchor="w", padx=8, pady=(0, 6))
        ttk.Button(f1, text="Проверить распознавание", command=self._check).pack(fill="x", padx=8, pady=(0, 8))

        f2 = ttk.LabelFrame(left, text="2. Игра")
        f2.pack(fill="x", **pad)
        self.start_btn = tk.Button(f2, text="▶  Старт  (F8)", font=("Segoe UI", 13, "bold"),
                                   bg="#3ddc84", activebackground="#2fbf70", relief="flat",
                                   command=self._toggle)
        self.start_btn.pack(fill="x", padx=8, pady=8, ipady=6)
        self.state_lbl = ttk.Label(f2, text="Остановлен", font=("Segoe UI", 10, "bold"))
        self.state_lbl.pack(anchor="w", padx=8)
        self.stats_lbl = ttk.Label(f2, text="", wraplength=260)
        self.stats_lbl.pack(anchor="w", padx=8, pady=(0, 8))

        f3 = ttk.LabelFrame(left, text="Настройки")
        f3.pack(fill="x", **pad)
        self.throw = tk.StringVar(value=self.cfg.get("throw", "space"))
        ttk.Label(f3, text="Бросок оружия:").pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Radiobutton(f3, text="пробелом (летит вверх)", value="space", variable=self.throw,
                        command=self._save_settings).pack(anchor="w", padx=16)
        ttk.Radiobutton(f3, text="кликом по монстру (летит к курсору)", value="click", variable=self.throw,
                        command=self._save_settings).pack(anchor="w", padx=16)
        self.restart = tk.BooleanVar(value=self.cfg.get("restart", True))
        ttk.Checkbutton(f3, text="Сам нажимать «Играть заново»", variable=self.restart,
                        command=self._save_settings).pack(anchor="w", padx=8, pady=(6, 0))
        ttk.Checkbutton(f3, text="Показывать, что видит бот", variable=self.show_preview,
                        command=self._preview_toggled).pack(anchor="w", padx=8)
        ttk.Label(f3, text="Задержка реакции (если промахивается — увеличь):").pack(anchor="w", padx=8, pady=(6, 0))
        self.latency = tk.DoubleVar(value=self.cfg.get("physics", {}).get("latency", 0.06) * 1000)
        row = ttk.Frame(f3)
        row.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Scale(row, from_=20, to=150, variable=self.latency, command=lambda v: self._latency_moved()).pack(
            side="left", fill="x", expand=True)
        self.latency_lbl = ttk.Label(row, width=7)
        self.latency_lbl.pack(side="left")
        self._latency_moved(save=False)

        f4 = ttk.LabelFrame(left, text="Журнал")
        f4.pack(fill="both", **pad)
        self.log = tk.Text(f4, width=40, height=7, state="disabled", font=("Consolas", 9), wrap="word")
        self.log.pack(fill="both", padx=6, pady=6)

        ttk.Label(left, text="F8 — старт/пауза в любой момент.\nОкно бота не должно закрывать игру.",
                  foreground="#666").pack(anchor="w", **pad)

        self.preview = tk.Label(self.root, bg="#222", width=30, text="Здесь будет\nкартинка игры",
                                fg="#aaa")
        self.preview.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

    def _add_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", time.strftime("%H:%M:%S ") + text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _update_region_label(self):
        r = self.cfg.get("region")
        if r:
            self.region_lbl.configure(text=f"Выбрано: {r['width']}×{r['height']} в точке ({r['left']}, {r['top']})")
        else:
            self.region_lbl.configure(text="Область ещё не выбрана.")

    # --- действия --------------------------------------------------------
    def _pick_region(self):
        self.engine.pause()
        self.root.withdraw()
        self.root.after(250, lambda: RegionPicker(self.root, self._region_done))

    def _region_done(self, region):
        self.root.deiconify()
        if region:
            self.cfg["region"] = region
            engine.save_config(self.cfg)
            self._update_region_label()
            self._add_log("Область игры сохранена.")
            self._check()

    def _check(self):
        r = self.cfg.get("region")
        if not r:
            self._add_log("Сначала выбери область игры.")
            return
        frame, sc = engine.check_region(r)
        self._show(draw_debug(frame, sc))
        msg = (f"Платформ: {len(sc.platforms)}, герой: {'найден' if sc.player else 'НЕ найден'}, "
               f"монстров: {len(sc.monsters)}, дыр: {len(sc.holes)}")
        if sc.game_over:
            msg = "Виден экран «Падение» — это нормально, бот сам нажмёт «Играть заново»."
        elif not sc.platforms:
            msg += "\nПлатформ не видно: проверь, что игра открыта и область выбрана точно по ней."
        self._add_log(msg)

    def _toggle(self):
        if self.engine.running:
            self.engine.pause()
            return
        if not self.cfg.get("region"):
            self._add_log("Сначала выбери область игры (кнопка выше).")
            return
        self._save_settings()
        self._move_aside()
        if self.engine.start():
            # Делаем окно игры активным, иначе нажатия уйдут в окно бота.
            r = self.cfg["region"]
            ctl = engine.Controls(self.cfg, r)
            ctl.ms.position = (r["left"] + r["width"] // 2, r["top"] + int(r["height"] * 0.3))
            ctl.ms.click(engine.mouse.Button.left)

    def _move_aside(self):
        """Отодвигаем окно бота, если оно перекрывает игру."""
        r = self.cfg["region"]
        self.root.update_idletasks()
        x, y = self.root.winfo_rootx(), self.root.winfo_rooty()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        overlap = not (x + w <= r["left"] or x >= r["left"] + r["width"]
                       or y + h <= r["top"] or y >= r["top"] + r["height"])
        if not overlap:
            return
        sw = self.root.winfo_screenwidth()
        if r["left"] + r["width"] + w + 10 <= sw:
            nx = r["left"] + r["width"] + 10
        elif r["left"] - w - 10 >= 0:
            nx = r["left"] - w - 10
        else:
            self._add_log("Окно бота перекрывает игру — передвинь его в сторону.")
            return
        self.root.geometry(f"+{nx}+{max(0, r['top'])}")

    def _save_settings(self):
        self.cfg["throw"] = self.throw.get()
        self.cfg["restart"] = bool(self.restart.get())
        self.cfg.setdefault("physics", {})["latency"] = round(self.latency.get() / 1000, 3)
        engine.save_config(self.cfg)

    def _latency_moved(self, save=True):
        self.latency_lbl.configure(text=f"{self.latency.get():.0f} мс")
        if save:
            self._save_settings()

    def _preview_toggled(self):
        if not self.show_preview.get():
            self.preview.configure(image="", text="Картинка\nвыключена")
            self.preview_img = None

    def _show(self, bgr):
        h, w = bgr.shape[:2]
        scale = PREVIEW_H / h
        rgb = cv2.cvtColor(cv2.resize(bgr, (int(w * scale), PREVIEW_H)), cv2.COLOR_BGR2RGB)
        self.preview_img = ImageTk.PhotoImage(Image.fromarray(rgb))
        self.preview.configure(image=self.preview_img, text="", width=self.preview_img.width())

    def _start_hotkeys(self):
        def on_press(k):
            if k == keyboard.Key.f8:
                self.root.after(0, self._hotkey_toggle)

        self.hotkeys = keyboard.Listener(on_press=on_press)
        self.hotkeys.daemon = True
        self.hotkeys.start()
        # Запасной вариант, если глобальный перехват не сработал.
        self.root.bind_all("<F8>", lambda e: self._hotkey_toggle())
        self._last_hotkey = 0.0

    def _hotkey_toggle(self):
        # Одно нажатие может прийти и через перехват, и через окно — считаем один раз.
        now = time.monotonic()
        if now - self._last_hotkey < 0.4:
            return
        self._last_hotkey = now
        # По F8 игра уже активна (её выбрал пользователь) — кликать не нужно.
        if self.engine.running:
            self.engine.pause()
        else:
            self._save_settings()
            self.engine.start()

    def _tick(self):
        while not self.logq.empty():
            self._add_log(self.logq.get())
        st = self.engine.stats
        if self.engine.running:
            self.start_btn.configure(text="⏸  Пауза  (F8)", bg="#ffb74d", activebackground="#f0a030")
            self.state_lbl.configure(text="Играет")
            self.stats_lbl.configure(
                text=f"{st['fps']:.0f} кадров/с, игр сыграно: {st['games']}\n"
                     f"{'герой виден' if st['player'] else 'героя не видно'}: {st['note']}")
            if self.show_preview.get() and self.engine.last_preview is not None:
                self._show(self.engine.last_preview)
                self.engine.last_preview = None
        else:
            self.start_btn.configure(text="▶  Старт  (F8)", bg="#3ddc84", activebackground="#2fbf70")
            self.state_lbl.configure(text="Остановлен")
        self.root.after(150, self._tick)

    def _quit(self):
        self.engine.stop()
        try:
            self.hotkeys.stop()
        except Exception:
            pass
        self.root.destroy()

    def run(self):
        self.root.mainloop()


def main():
    try:
        App().run()
    except Exception as e:  # в .exe без консоли ошибку иначе не увидеть
        import traceback
        from tkinter import messagebox
        messagebox.showerror(APP_TITLE, f"Ошибка запуска:\n{e!r}\n\n{traceback.format_exc()[-1500:]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
