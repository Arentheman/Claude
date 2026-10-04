"""
Окно-запускалка для бота: никаких команд и настроек.

Бот сам находит игру на экране. Кнопку «Играть снова» он узнаёт, подсмотрев,
куда вы нажмёте после первого проигрыша, и дальше перезапускает игру сам.
"""
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

import bot

PREVIEW_H = 520


class State:
    def __init__(self):
        self.quit = False      # остановить текущий сеанс (имя совпадает с тем, что ждёт bot.play_run)
        self.paused = False


class LogWriter:
    def __init__(self, q):
        self.q = q

    def write(self, s):
        if s.strip():
            self.q.put(("log", s.rstrip()))

    def flush(self):
        pass


def load_cfg():
    try:
        with open(bot.CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_cfg(cfg):
    try:
        with open(bot.CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Не удалось сохранить настройки:", e)


def game_running(scr, det):
    d = det.detect(scr.grab())
    return d["player"] is not None and len(d["plats"]) >= 3


class Worker:
    def __init__(self, app, mode):
        self.app, self.mode = app, mode
        self.st = app.state
        self.q = app.q

    def status(self, text):
        self.q.put(("status", text))

    def stats(self, **kw):
        self.q.put(("stats", kw))

    def run(self):
        try:
            self._run()
        except Exception as e:  # показать ошибку в окне, а не молча упасть
            import traceback
            traceback.print_exc(file=LogWriter(self.q))
            self.status(f"Ошибка: {e}")
        finally:
            self.q.put(("done", None))

    def locate(self):
        """Ищет светлую полосу игры между тёмными полями Telegram на всех мониторах."""
        scr = bot.Screen()
        while not self.st.quit:
            self.app.hide_and_wait()  # окно бота не должно закрывать игру на снимке
            found = None
            for i in range(1, len(scr.sct.monitors)):
                img, mon = scr.monitor(i)
                reg = bot.find_game_region(img)
                if reg:
                    found = {"left": reg["left"] + mon["left"], "top": reg["top"] + mon["top"],
                             "width": reg["width"], "height": reg["height"]}
                    break
            self.q.put(("place", found))
            if found:
                scr.region = found
                return scr
            self.status("Не вижу игру. Откройте её в Telegram Desktop, чтобы она была целиком видна на экране.")
            time.sleep(1.5)
        return None

    def wait_for_game(self, scr, text):
        det = bot.Detector()
        self.status(text)
        ok_since = None
        while not self.st.quit:
            if game_running(scr, det):
                ok_since = ok_since or time.time()
                if time.time() - ok_since > 0.5:
                    return True
            else:
                ok_since = None
            time.sleep(0.05)
        return False

    def restart(self, scr, ctl, cfg):
        reg = scr.region
        clicks = cfg.get("restart_clicks") or []
        if clicks:
            self.status("Перезапускаю игру…")
            det = bot.Detector()
            for _ in range(3):
                time.sleep(1.5)
                for rx, ry in clicks:
                    ctl.click(rx * reg["width"], ry * reg["height"])
                    time.sleep(0.6)
                t0 = time.time()
                while time.time() - t0 < 5 and not self.st.quit:
                    if game_running(scr, det):
                        return True
                    time.sleep(0.1)
            print("Запомненная кнопка не сработала — покажите заново")
        # Подсматриваем, куда человек нажмёт для рестарта
        seen = []
        try:
            from pynput import mouse

            def on_click(x, y, button, pressed):
                if pressed and button == mouse.Button.left:
                    seen.append((x, y))
            listener = mouse.Listener(on_click=on_click)
            listener.start()
        except Exception:
            listener = None
        ok = self.wait_for_game(scr, "Перезапустите игру сами: нажмите «Играть снова».\n"
                                     "Бот запомнит, куда вы нажали, и дальше будет делать это сам.")
        if listener:
            listener.stop()
        inside = [[round((x - reg["left"]) / reg["width"], 4), round((y - reg["top"]) / reg["height"], 4)]
                  for x, y in seen
                  if reg["left"] <= x < reg["left"] + reg["width"] and reg["top"] <= y < reg["top"] + reg["height"]]
        if ok and inside:
            cfg["restart_clicks"] = inside
            save_cfg(cfg)
            print(f"Запомнил кнопку рестарта: {inside}")
        return ok

    def _run(self):
        self.status("Ищу игру на экране…")
        scr = self.locate()
        if scr is None:
            return
        cfg = load_cfg()
        cfg["region"] = scr.region
        save_cfg(cfg)
        print(f"Нашёл игру: {scr.region}")
        watch = self.mode == "watch"
        ctl = bot.Controls(scr.region, dry=watch)
        on_frame = self.app.set_frame

        if watch:
            self.status("Бот только смотрит и ничего не нажимает. Поиграйте сами и проверьте рамки на картинке.")
            while not self.st.quit:
                bot.play_run(scr, ctl, self.st, None, show=False, act=False, on_frame=on_frame)
            return

        pop = bot.Population()
        genome = None
        if self.mode == "play":
            genome = pop.best
            if genome is None:
                with open(bot.PRETRAINED_PATH, encoding="utf-8") as f:
                    genome = np.array(json.load(f)["genomes"][0])

        if not self.wait_for_game(scr, "Начните игру в Telegram. Бот подхватит управление, как только она пойдёт."):
            return
        while not self.st.quit:
            if self.mode == "train":
                g = pop.current()
                info = f"gen {pop.gen} net {pop.idx + 1}/{len(pop.genomes)}"
                self.status(f"Учусь: поколение {pop.gen}, попытка {pop.idx + 1} из {len(pop.genomes)}.\n"
                            "Не трогайте мышь и клавиатуру. F9 — пауза, F10 — стоп.")
            else:
                g, info = genome, "best net"
                self.status("Играет лучшая сеть. F9 — пауза, F10 — стоп.")
            tr = bot.play_run(scr, ctl, self.st, g, show=False, info=info, on_frame=on_frame)
            if self.st.quit:
                break
            fit = tr.fitness()
            print(f"Попытка: высота {tr.height_label()} px, монстров {tr.kills}, очки {fit:.0f}")
            if self.mode == "train":
                pop.report(fit, tr.max_h, tr.kills)
            self.stats(gen=pop.gen, best=pop.best_fit, last=fit)
            if not self.restart(scr, ctl, cfg):
                break
        ctl.release()


class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.state = State()
        self.worker = None
        self.frame = None
        self.photo = None
        sys.stdout = sys.stderr = LogWriter(self.q)

        root.title("Нейро-прыгун")
        root.configure(bg="#f4f6f8")
        root.minsize(680, 600)
        style = ttk.Style()
        style.configure("Big.TButton", font=("Segoe UI", 12), padding=8)
        style.configure("TLabel", background="#f4f6f8")

        left = tk.Frame(root, bg="#1d2733", width=250, height=PREVIEW_H)
        left.pack(side="left", fill="y", padx=12, pady=12)
        left.pack_propagate(False)
        self.preview = tk.Label(left, bg="#1d2733", fg="#cfd8e3", font=("Segoe UI", 11), wraplength=220,
                                text="Здесь будет видно,\nчто распознаёт бот")
        self.preview.pack(expand=True, fill="both")

        right = tk.Frame(root, bg="#f4f6f8")
        right.pack(side="left", fill="both", expand=True, padx=(0, 12), pady=12)
        tk.Label(right, text="Нейро-прыгун", font=("Segoe UI", 20, "bold"), bg="#f4f6f8", fg="#1d2733").pack(anchor="w")
        tk.Label(right, text="Откройте игру в Telegram Desktop\nи нажмите «Учиться».", justify="left",
                 font=("Segoe UI", 11), bg="#f4f6f8", fg="#566371").pack(anchor="w", pady=(0, 10))

        btns = tk.Frame(right, bg="#f4f6f8")
        btns.pack(anchor="w", pady=4)
        self.b_train = ttk.Button(btns, text="▶  Учиться", style="Big.TButton", command=lambda: self.start("train"))
        self.b_play = ttk.Button(btns, text="Играть лучшей сетью", style="Big.TButton", command=lambda: self.start("play"))
        self.b_watch = ttk.Button(btns, text="Проверить зрение", style="Big.TButton", command=lambda: self.start("watch"))
        self.b_stop = ttk.Button(btns, text="■  Стоп (F10)", style="Big.TButton", command=self.stop, state="disabled")
        for i, b in enumerate((self.b_train, self.b_play, self.b_watch, self.b_stop)):
            b.grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 8), pady=(0, 8))

        self.status = tk.Label(right, text="Готов.", font=("Segoe UI", 12), bg="#ffffff", fg="#1d2733",
                               justify="left", anchor="nw", wraplength=380, padx=12, pady=10, relief="solid", bd=1)
        self.status.pack(fill="x", pady=12)
        self.stats = tk.Label(right, text="", font=("Consolas", 10), bg="#f4f6f8", fg="#1d2733", justify="left",
                              wraplength=400)
        self.stats.pack(anchor="w")
        self.log = tk.Text(right, height=12, width=50, wrap="word", font=("Consolas", 9), bg="#ffffff", fg="#334", relief="solid", bd=1)
        self.log.pack(fill="both", expand=True, pady=(8, 0))
        self.show_saved_stats()

        self._hotkeys()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(50, self.poll)

    def show_saved_stats(self):
        try:
            with open(bot.STATE_PATH, encoding="utf-8") as f:
                s = json.load(f)
            self.stats.config(text=f"Поколение {s['gen']}   рекорд {max(0, s.get('best_fit', 0)):.0f} очков")
        except Exception:
            self.stats.config(text="Обучение ещё не начиналось: стартуем с сетей, обученных в симуляторе.")

    def _hotkeys(self):
        try:
            from pynput import keyboard

            def on_press(key):
                if key == keyboard.Key.f9 and self.worker:
                    self.state.paused = not self.state.paused
                    print("Пауза" if self.state.paused else "Продолжаю")
                elif key == keyboard.Key.f10:
                    self.state.quit = True
            listener = keyboard.Listener(on_press=on_press)
            listener.daemon = True
            listener.start()
        except Exception as e:
            print("Горячие клавиши не работают:", e)

    def start(self, mode):
        if self.worker:
            return
        self.state = State()
        w = Worker(self, mode)
        self.worker = threading.Thread(target=w.run, daemon=True)
        self.worker.start()
        for b in (self.b_train, self.b_play, self.b_watch):
            b.config(state="disabled")
        self.b_stop.config(state="normal")

    def stop(self):
        self.state.quit = True

    def hide_and_wait(self):
        """Вызывается из рабочего потока: прячет окно и ждёт, пока оно исчезнет с экрана."""
        ev = threading.Event()
        self.q.put(("hide", ev))
        ev.wait(3)
        time.sleep(0.4)

    def place_beside(self, reg):
        self.root.deiconify()
        if not reg:
            return
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        if reg["left"] >= w + 10:
            x = reg["left"] - w - 10
        elif sw - (reg["left"] + reg["width"]) >= w + 10:
            x = reg["left"] + reg["width"] + 10
        else:
            x = 0
            print("Окно бота не помещается рядом с игрой — сдвиньте его, чтобы оно не закрывало игру")
        self.root.geometry(f"+{x}+{max(0, reg['top'])}")

    def set_frame(self, img, tr):
        self.frame = img  # рисуется в главном потоке в poll()

    def poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "hide":
                    self.root.withdraw()
                    self.root.update()
                    val.set()
                elif kind == "place":
                    self.place_beside(val)
                elif kind == "log":
                    self.log.insert("end", time.strftime("%H:%M:%S ") + val + "\n")
                    self.log.see("end")
                elif kind == "status":
                    self.status.config(text=val)
                elif kind == "stats":
                    self.stats.config(text=f"Поколение {val['gen']}   рекорд {max(0, val['best']):.0f}   последняя попытка {val['last']:.0f}")
                elif kind == "done":
                    self.worker = None
                    for b in (self.b_train, self.b_play, self.b_watch):
                        b.config(state="normal")
                    self.b_stop.config(state="disabled")
                    if not self.status.cget("text").startswith("Ошибка"):
                        self.status.config(text="Остановлено. Прогресс сохранён.")
        except queue.Empty:
            pass
        if self.frame is not None:
            img, self.frame = self.frame, None
            h, w = img.shape[:2]
            scale = min(PREVIEW_H / h, 246 / w)
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            self.photo = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB)))
            self.preview.config(image=self.photo, text="")
        self.root.after(50, self.poll)

    def on_close(self):
        self.state.quit = True
        self.root.after(300, self.root.destroy)


def main():
    bot.set_dpi_aware()
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
