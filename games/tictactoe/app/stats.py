"""Статистика игрока: по полю и уровню - партии, победы, поражения, ничьи, серия побед."""
from games.tictactoe.app.storage import is_int, load_json, save_json

RESULTS = ("win", "loss", "draw")
FIELDS = ("games", "wins", "losses", "draws", "streak", "best_streak")


def key(size, level):
    return f"{size}x{size}/{level}"


def empty():
    return {f: 0 for f in FIELDS}


class Stats:
    def __init__(self, data=None):
        self.data = data or {}

    def entry(self, size, level):
        return dict(self.data.get(key(size, level), empty()))

    def record(self, size, level, result):
        """result - с точки зрения игрока: 'win', 'loss' или 'draw'. Ничья и поражение
        обрывают серию побед."""
        if result not in RESULTS:
            raise ValueError(f"неизвестный итог партии: {result!r}")
        e = self.entry(size, level)
        e["games"] += 1
        e[{"win": "wins", "loss": "losses", "draw": "draws"}[result]] += 1
        e["streak"] = e["streak"] + 1 if result == "win" else 0
        e["best_streak"] = max(e["best_streak"], e["streak"])
        self.data[key(size, level)] = e
        return e

    def totals(self):
        out = empty()
        for e in self.data.values():
            for f in ("games", "wins", "losses", "draws"):
                out[f] += e[f]
        out["best_streak"] = max([e["best_streak"] for e in self.data.values()] or [0])
        return out

    @classmethod
    def load(cls, path):
        """Битый файл - пустая статистика; битая запись - пропускается."""
        raw = load_json(path)
        data = {}
        if isinstance(raw, dict):
            for k, e in raw.items():
                if isinstance(e, dict) and all(is_int(e.get(f)) and e[f] >= 0 for f in FIELDS):
                    data[k] = {f: e[f] for f in FIELDS}
        return cls(data)

    def save(self, path):
        return save_json(path, self.data)
