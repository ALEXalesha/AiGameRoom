"""Настройки и статистика игрока: settings.json и stats.json в папке данных.

Запись атомарная (временный файл и замена). Битый или чужой файл не роняет игру - берутся
значения по умолчанию; числа за пределами обрезаются к пределам.
"""
import json
import math
import os

LEVELS = ("novice", "medium", "strong")
LEVEL_NAMES = {"novice": "Новичок", "medium": "Средний", "strong": "Сильный"}

SPEED_RANGE = (60, 250)
VOLUME_RANGE = (0, 100)
PALETTE_RANGE = (0, 2)

DEFAULT_SETTINGS = {"speed_ms": 110, "opponent": "medium", "volume": 60, "palette": 0,
                    "show_food_map": False}

LEVEL_COUNTERS = ("wins", "losses", "draws", "match_wins", "match_losses")
TOTAL_COUNTERS = ("matches", "rounds", "longest", "food")


def empty_stats():
    stats = {k: 0 for k in TOTAL_COUNTERS}
    stats["levels"] = {lv: {k: 0 for k in LEVEL_COUNTERS} for lv in LEVELS}
    return stats


def _number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _clip(v, bounds, default):
    if not _number(v):
        return default
    return int(min(max(round(v), bounds[0]), bounds[1]))


def clean_settings(raw):
    raw = raw if isinstance(raw, dict) else {}
    d = DEFAULT_SETTINGS
    opponent = raw.get("opponent")
    food_map = raw.get("show_food_map")
    return {
        "speed_ms": _clip(raw.get("speed_ms"), SPEED_RANGE, d["speed_ms"]),
        "opponent": opponent if opponent in LEVELS else d["opponent"],
        "volume": _clip(raw.get("volume"), VOLUME_RANGE, d["volume"]),
        "palette": _clip(raw.get("palette"), PALETTE_RANGE, d["palette"]),
        "show_food_map": food_map if isinstance(food_map, bool) else d["show_food_map"],
    }


def _count(v):
    return int(v) if _number(v) and v > 0 else 0


def clean_stats(raw):
    raw = raw if isinstance(raw, dict) else {}
    stats = empty_stats()
    for k in TOTAL_COUNTERS:
        stats[k] = _count(raw.get(k))
    levels = raw.get("levels") if isinstance(raw.get("levels"), dict) else {}
    for lv in LEVELS:
        got = levels.get(lv) if isinstance(levels.get(lv), dict) else {}
        for k in LEVEL_COUNTERS:
            stats["levels"][lv][k] = _count(got.get(k))
    return stats


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None


def write_json(path, data):
    """Через временный файл: убитый посреди записи процесс оставит прежний файл."""
    path = os.fspath(path)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def load_settings(path):
    return clean_settings(_read_json(path))


def save_settings(path, settings):
    return write_json(path, clean_settings(settings))


def load_stats(path):
    return clean_stats(_read_json(path))


def save_stats(path, stats):
    return write_json(path, clean_stats(stats))


def record_round(stats, level, result, player_length, food):
    """result - 'win' / 'lose' / 'draw' с точки зрения игрока; food - съел игрок за раунд."""
    lv = stats["levels"][level]
    lv[{"win": "wins", "lose": "losses", "draw": "draws"}[result]] += 1
    stats["rounds"] += 1
    stats["longest"] = max(stats["longest"], int(player_length))
    stats["food"] += int(food)
    return stats


def record_match(stats, level, won):
    stats["matches"] += 1
    stats["levels"][level]["match_wins" if won else "match_losses"] += 1
    return stats


class Store:
    """Настройки и статистика одной папки данных. set() пишет файл сразу."""

    def __init__(self, folder):
        self.folder = os.fspath(folder)
        self.settings_path = os.path.join(self.folder, "settings.json")
        self.stats_path = os.path.join(self.folder, "stats.json")
        self.window_path = os.path.join(self.folder, "window.json")
        self.settings = load_settings(self.settings_path)
        self.stats = load_stats(self.stats_path)

    def set(self, key, value):
        self.settings = clean_settings({**self.settings, key: value})
        save_settings(self.settings_path, self.settings)
        return self.settings[key]

    def save_stats(self):
        return save_stats(self.stats_path, self.stats)
