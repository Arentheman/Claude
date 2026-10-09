"""Запись игры бота для разбора ошибок.

Пишет в отдельную папку (и в конце упаковывает в zip):
  deaths/attempt_NN.mp4 — последние ~8 с перед каждым падением, полный размер,
                          с разметкой (что бот видел и что решил);
  timeline.mp4          — вся сессия, уменьшенная, 5 кадров/с;
  telemetry.jsonl.gz    — по кадру: позиция, скорость, цель, решения, физика;
  summary.json          — попытки, длительность, причины.

Работает в своём потоке, чтобы не замедлять бота: главный цикл только
кладёт кадры в очередь (если запись не успевает — лишние кадры пропускаются).
"""
import collections
import gzip
import json
import os
import queue
import threading
import time
import zipfile

import cv2

from vision import draw_debug

CLIP_SECONDS = 8.0          # сколько секунд до падения сохранять
CLIP_FPS = 20.0             # ролики падений: кадров в секунду
CLIP_W = 366                # и ширина (3/4 от игровой) — чтобы zip был небольшим
TIMELINE_FPS = 4.0
TIMELINE_W = 220


def default_root():
    # Только латиница: OpenCV на Windows не пишет видео по пути с кириллицей.
    docs = os.path.join(os.path.expanduser("~"), "Documents")
    base = docs if os.path.isdir(docs) else os.path.expanduser("~")
    return os.path.join(base, "DoodleBot recordings")


def _writer(path, fps, size):
    """MP4 (MPEG-4): работает в любой сборке OpenCV без дополнительных библиотек."""
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not w.isOpened():
        raise RuntimeError("не удалось создать видеофайл " + path)
    return w


def _r(v, n=1):
    return None if v is None else round(float(v), n)


class Recorder:
    def __init__(self, root=None, log=print):
        self.log = log
        stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        self.dir = os.path.join(root or default_root(), f"rec_{stamp}")
        os.makedirs(os.path.join(self.dir, "deaths"), exist_ok=True)
        self.q = queue.Queue(maxsize=90)
        self.dropped = 0
        self._stop = False
        self.attempt = 1
        self.t0 = None
        self.ring = collections.deque()          # (t, jpeg) за последние CLIP_SECONDS
        self.timeline = None
        self.last_tl = -1e9
        self.was_over = False
        self.attempts = []                       # итоги попыток
        self.attempt_start = None
        self.max_height = 0.0
        self.tel = gzip.open(os.path.join(self.dir, "telemetry.jsonl.gz"), "wt", encoding="utf-8")
        self.thread = threading.Thread(target=self._work, daemon=True)
        self.thread.start()

    # --- из игрового цикла ------------------------------------------------
    def feed(self, t, frame, sc, plan, planner):
        """Неблокирующая передача кадра. Данные планировщика снимаем сразу,
        пока они соответствуют этому кадру."""
        info = None
        if planner is not None and plan is not None:
            info = {
                "vy": _r(planner.vy), "vx": _r(planner.vx), "world": _r(planner.world),
                "drift": _r(planner.drift), "hunting": bool(planner.hunting),
                "jump_v": _r(planner.ph.jump_speed), "run_v": _r(planner.ph.run_speed),
                "move": plan.move, "fire": plan.fire, "note": plan.note,
                "target": None if plan.target is None else [_r(plan.target[0]), _r(plan.target[1])],
            }
        try:
            self.q.put_nowait((t, frame, sc, plan, info))
        except queue.Full:
            self.dropped += 1

    def stop(self):
        """Дописывает всё и упаковывает в zip. Возвращает путь к zip."""
        self._stop = True
        self.thread.join(timeout=30)
        return self._finish()

    # --- поток записи -------------------------------------------------------
    def _work(self):
        while not (self._stop and self.q.empty()):
            try:
                item = self.q.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                self._handle(*item)
            except Exception as e:      # запись не должна ронять бота
                self.log(f"Запись: ошибка {e!r}")

    def _handle(self, t, frame, sc, plan, info):
        if self.t0 is None:
            self.t0 = t
            self.attempt_start = t
        rel = t - self.t0
        img = draw_debug(frame, sc, plan)
        h, w = img.shape[:2]
        # Шапка: номер попытки и время — чтобы ссылаться на моменты.
        cv2.rectangle(img, (0, 0), (w, 26), (0, 0, 0), -1)
        cv2.putText(img, f"attempt {self.attempt}  t={rel:7.2f}s", (6, 18),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

        if not self.ring or t - self.ring[-1][0] >= 1.0 / CLIP_FPS - 1e-3:
            clip = cv2.resize(img, (CLIP_W, int(h * CLIP_W / w)), interpolation=cv2.INTER_AREA)
            ok, jpg = cv2.imencode(".jpg", clip, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if ok:
                self.ring.append((t, jpg))
        while self.ring and t - self.ring[0][0] > CLIP_SECONDS:
            self.ring.popleft()

        if t - self.last_tl >= 1.0 / TIMELINE_FPS:
            small = cv2.resize(img, (TIMELINE_W, int(h * TIMELINE_W / w)), interpolation=cv2.INTER_AREA)
            if self.timeline is None:
                self.tl_size = (small.shape[1], small.shape[0])
                self.timeline = _writer(os.path.join(self.dir, "timeline.mp4"), TIMELINE_FPS, self.tl_size)
            if (small.shape[1], small.shape[0]) == self.tl_size:
                self.timeline.write(small)
            self.last_tl = t

        if info is not None and info["world"] is not None:
            # world — накопленная прокрутка экрана вверх = пройденная высота, px
            self.max_height = max(self.max_height, info["world"])

        rec = {"t": round(rel, 3), "a": self.attempt}
        if sc.player is not None:
            rec["p"] = [_r(sc.player.x), _r(sc.player.y)]
        rec["plats"] = [[_r(p.x, 0), _r(p.y, 0), int(p.broken), int(p.bonus), _r(p.vx, 0)] for p in sc.platforms]
        if sc.monsters:
            rec["mons"] = [[_r(m.x, 0), _r(m.y, 0), _r(m.w, 0), _r(m.h, 0)] for m in sc.monsters]
        if sc.holes:
            rec["holes"] = [[_r(m.x, 0), _r(m.y, 0), _r(m.w, 0)] for m in sc.holes]
        if sc.game_over:
            rec["over"] = 1
        if info:
            rec.update(info)
        self.tel.write(json.dumps(rec, ensure_ascii=False) + "\n")

        over = sc.game_over is not None
        if over and not self.was_over:
            self._save_death(t)
        if not over and self.was_over:
            self.attempt += 1
            self.attempt_start = t
            self.max_height = 0.0
        self.was_over = over

    def _save_death(self, t):
        frames = list(self.ring)
        if len(frames) >= 2:
            fps = max(5.0, min(60.0, (len(frames) - 1) / max(1e-3, frames[-1][0] - frames[0][0])))
            first = cv2.imdecode(frames[0][1], cv2.IMREAD_COLOR)
            path = os.path.join(self.dir, "deaths", f"attempt_{self.attempt:02d}.mp4")
            w = _writer(path, fps, (first.shape[1], first.shape[0]))
            for _, jpg in frames:
                w.write(cv2.imdecode(jpg, cv2.IMREAD_COLOR))
            w.release()
        dur = t - (self.attempt_start or t)
        self.attempts.append({"attempt": self.attempt, "duration_s": round(dur, 1),
                              "height_px": round(self.max_height)})
        self.log(f"Запись: падение в попытке {self.attempt} сохранено")

    def _finish(self):
        if self.timeline is not None:
            self.timeline.release()
        self.tel.close()
        summary = {"attempts": self.attempts, "dropped_frames": self.dropped,
                   "unfinished_attempt": self.attempt if not self.was_over else None}
        with open(os.path.join(self.dir, "summary.json"), "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        zpath = self.dir + ".zip"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(self.dir):
                for name in files:
                    full = os.path.join(root, name)
                    z.write(full, os.path.relpath(full, os.path.dirname(self.dir)))
        return zpath
