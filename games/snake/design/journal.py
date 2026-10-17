"""Журнал сетей-оформителей: сколько раскладок и наборов тайлов дали сети, сколько раз
пришлось пересэмплировать и сколько раз сработал запасной вариант кода, насколько окно
отличается от кодового. Файл ai_ui.json в папке данных игры (ctx.data_dir).

Запись тихая: в окне ничего не всплывает, числа видны в «Статистике». На диск - сразу при
запасном варианте (редко) и при остановке игры; обычные счётчики копятся в памяти, чтобы
перетаскивание края окна не писало файл на каждый пиксель.
"""
import datetime
import math
import os

from aikit.storage import load_json, save_json

FILE = "ai_ui.json"
COUNTERS = ("layouts", "layout_resamples", "layout_fallbacks", "tile_sets", "tile_resamples",
            "tile_fallbacks", "tile_misses")
LAST = 10


def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) and v >= 0


def empty():
    data = {k: 0 for k in COUNTERS}
    data.update({"deviation_sum": 0.0, "deviation_n": 0, "last": []})
    return data


def clean(raw):
    data = empty()
    if not isinstance(raw, dict):
        return data
    for k in COUNTERS + ("deviation_n",):
        if _num(raw.get(k)):
            data[k] = int(raw[k])
    if _num(raw.get("deviation_sum")):
        data["deviation_sum"] = float(raw["deviation_sum"])
    last = raw.get("last")
    if isinstance(last, list):
        data["last"] = [e for e in last if isinstance(e, dict) and isinstance(e.get("what"), str)
                        and isinstance(e.get("why"), str)][-LAST:]
    return data


class Journal:
    def __init__(self, data_dir=None):
        self.path = os.path.join(os.fspath(data_dir), FILE) if data_dir is not None else None
        self.data = clean(load_json(self.path)) if self.path else empty()

    def count(self, key, n=1):
        self.data[key] += n

    def deviation(self, px):
        self.data["deviation_sum"] += float(px)
        self.data["deviation_n"] += 1

    def note(self, what, why):
        """Запасной вариант сработал: what - «окно: меню» или «поле: палитра 0», why - причина."""
        when = datetime.datetime.now().isoformat(timespec="seconds")
        self.data["last"] = (self.data["last"] + [{"what": what, "why": str(why)[:300], "when": when}])[-LAST:]
        self.save()

    def mean_deviation(self):
        n = self.data["deviation_n"]
        return self.data["deviation_sum"] / n if n else None

    def save(self):
        if self.path:
            save_json(self.path, self.data)
