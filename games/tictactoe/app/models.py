"""Обученные сети и их паспорта из папки models (рядом с кодом или внутри сборки)."""
import json
from functools import lru_cache

from games.tictactoe import paths
from games.tictactoe.core import net

LEVELS = ("novice", "medium", "strong")
LEVEL_NAMES = {"novice": "новичок", "medium": "средний", "strong": "сильный"}


@lru_cache(maxsize=None)
def load(size, level):
    return net.ValueNet.load(paths.resource("models", f"{size}x{size}-{level}.npz"))


@lru_cache(maxsize=None)
def passport(size):
    with open(paths.resource("models", f"{size}x{size}.json"), encoding="utf-8") as f:
        return json.load(f)
