"""Прогон распознавания и логики бота по записи экрана — для проверки и настройки.

  python analyze_video.py запись.mp4 [результат.mp4]

Запись должна содержать только игровое поле (как обрезанная запись из чата);
если на ней весь экран — укажи область: --crop x,y,w,h
"""
import argparse

import cv2

from planner import Physics, Planner
from vision import Detector, draw_debug


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out", nargs="?", default="analyzed.mp4")
    ap.add_argument("--crop", help="x,y,w,h области игры на записи")
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    det, planner = Detector(), Planner(Physics())
    writer = None
    n = found = 0
    crop = [int(v) for v in args.crop.split(",")] if args.crop else None
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if crop:
            x, y, w, h = crop
            frame = frame[y:y + h, x:x + w]
        t = n / fps
        sc = det.detect(frame, t)
        plan = None if sc.game_over else planner.step(sc, t)
        img = draw_debug(frame, sc, plan)
        if writer is None:
            writer = cv2.VideoWriter(args.out, cv2.VideoWriter_fourcc(*"mp4v"), fps, (img.shape[1], img.shape[0]))
        writer.write(img)
        n += 1
        found += sc.player is not None or sc.game_over is not None
    if writer:
        writer.release()
    print(f"Кадров: {n}, герой найден в {found} ({100 * found / max(n, 1):.0f}%). Результат: {args.out}")


if __name__ == "__main__":
    main()
