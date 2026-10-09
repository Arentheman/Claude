"""Консольный запуск бота (без окна). Обычно удобнее app.py / DoodleBot.exe.

  python bot.py --calibrate   — указать, где на экране игра (один раз)
  python bot.py               — запуск. F8 — старт/пауза, F10 — выход.
  python bot.py --debug       — то же + кадры с разметкой в папку debug/
"""
import argparse
import os
import time

import cv2

from engine import HERE, BotEngine, check_region, load_config, save_config
from pynput import keyboard, mouse
from vision import draw_debug


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
    cfg["region"] = {"left": min(x0, x1), "top": min(y0, y1),
                     "width": abs(x1 - x0), "height": abs(y1 - y0)}
    save_config(cfg)
    print("Сохранено:", cfg["region"])

    frame, sc = check_region(cfg["region"])
    out = os.path.join(HERE, "calibration_check.png")
    cv2.imwrite(out, draw_debug(frame, sc))
    print(f"Проверка: платформ {len(sc.platforms)}, герой {'найден' if sc.player else 'НЕ найден'}, "
          f"монстров {len(sc.monsters)}, дыр {len(sc.holes)}")
    print(f"Картинка с разметкой: {out}")


def run(cfg, save_debug=False):
    if not cfg.get("region"):
        print("Сначала откалибруй область игры: python bot.py --calibrate")
        return
    eng = BotEngine(cfg, debug_dir=os.path.join(HERE, "debug") if save_debug else None)
    eng.start_thread()
    done = []

    def on_press(k):
        if k == keyboard.Key.f8:
            eng.toggle()
        elif k == keyboard.Key.f10:
            done.append(1)
            return False

    listener = keyboard.Listener(on_press=on_press)
    listener.start()
    print("Готово. Кликни по игре (чтобы окно было активным) и нажми F8.")
    print("F8 — старт/пауза, F10 — выход.")
    try:
        last = time.time()
        while not done:
            time.sleep(0.2)
            if eng.running and time.time() - last > 5:
                print(f"{eng.stats['fps']:.0f} к/с; {eng.stats['note']}")
                last = time.time()
    except KeyboardInterrupt:
        pass
    finally:
        eng.stop()
        listener.stop()
    print("Выход.")


def main():
    ap = argparse.ArgumentParser(description="Бот для Doodle Jump (Telegram mini-app)")
    ap.add_argument("--calibrate", action="store_true", help="выбрать область игры на экране")
    ap.add_argument("--debug", action="store_true", help="сохранять кадры с разметкой в папку debug/")
    args = ap.parse_args()
    cfg = load_config()
    if args.calibrate:
        calibrate(cfg)
    else:
        run(cfg, save_debug=args.debug)


if __name__ == "__main__":
    main()
