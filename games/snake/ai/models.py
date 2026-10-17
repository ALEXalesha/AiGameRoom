"""Загрузка моделей и их паспортов из папки game/models (рядом с кодом или внутри сборки).

Нет файла или он битый - ModelMissing с понятным текстом для окна, а не падение.
"""
import json
import os

from games.snake.ui.store import LEVEL_NAMES, LEVELS

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models")


class ModelMissing(Exception):
    """Модель не найдена или не читается. Текст исключения показывается игроку."""


def _folder(folder):
    return MODELS_DIR if folder is None else os.fspath(folder)


def _need(path, what):
    if not os.path.isfile(path):
        raise ModelMissing(f"Нет файла {what}: {path}\nСначала обучите сеть (папка train).")


def load_world(folder=None):
    from games.snake.ai.world_net import WorldNet

    path = os.path.join(_folder(folder), "world.npz")
    _need(path, "сети-мира models/world.npz")
    try:
        return WorldNet.load(path)
    except Exception as err:  # noqa: BLE001 - любой сбой чтения - сообщение в окне
        raise ModelMissing(f"Не удалось прочитать models/world.npz: {err}") from err


def load_opponent(level, folder=None):
    if level not in LEVELS:
        raise ModelMissing(f"Неизвестный уровень соперника: {level}")
    name = f"player_{level}.npz"
    path = os.path.join(_folder(folder), name)
    _need(path, f"соперника «{LEVEL_NAMES[level]}» models/{name}")
    try:
        from games.snake.ai.player_net import PlayerNet     # лениво: модуль сети соперника пишется отдельно
    except ImportError as err:
        raise ModelMissing(f"Нет модуля сети соперника (game.ai.player_net): {err}") from err
    try:
        return PlayerNet.load(path)
    except Exception as err:  # noqa: BLE001
        raise ModelMissing(f"Не удалось прочитать models/{name}: {err}") from err


def _load_net(cls, name, what, folder):
    path = os.path.join(_folder(folder), name)
    _need(path, f"{what} models/{name}")
    try:
        return cls.load(path)
    except Exception as err:  # noqa: BLE001
        raise ModelMissing(f"Не удалось прочитать models/{name}: {err}") from err


def load_designer(folder=None):
    """Сеть-дизайнер окна (2.0). Нет - окно раскладывает код."""
    from games.snake.design.designer_net import DesignerNet     # прямой импорт: его видит PyInstaller
    return _load_net(DesignerNet, "designer.npz", "сети-дизайнера", folder)


def load_painter(folder=None):
    """Сеть-художник клеток поля (2.0). Нет - клетки рисует код."""
    from games.snake.design.painter_net import PainterNet
    return _load_net(PainterNet, "painter.npz", "сети-художника", folder)


def load_passport(name, folder=None):
    """models/<name>.json как словарь; нет файла, битый или не словарь - None."""
    path = os.path.join(_folder(folder), f"{name}.json")
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, UnicodeDecodeError, ValueError, RecursionError):
        return None
    return data if isinstance(data, dict) else None


class Models:
    """То же для окна: одна папка на всё (в тестах окну подсовывают подделку)."""

    def __init__(self, folder=None):
        self.folder = folder

    def load_world(self):
        return load_world(self.folder)

    def load_opponent(self, level):
        return load_opponent(level, self.folder)

    def load_designer(self):
        return load_designer(self.folder)

    def load_painter(self):
        return load_painter(self.folder)

    def load_passport(self, name):
        return load_passport(name, self.folder)
