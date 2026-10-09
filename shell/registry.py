"""Список игр: каждая папка games/<id>/ с __init__.py - игра.

Выбор (docs/games.md): игры лежат копиями в games/, а не путями к их папкам в файле-списке.
У каждой игры свой пакет `game`, два таких пакета в одной программе не уживаются, а копия
с переписанными импортами (tools/vendor_game.py) - это и есть перенос по spec.md.

Сломанная игра не роняет оболочку: её запись остаётся в списке с error - причиной.
"""
import importlib
import os
import sys
import traceback
from dataclasses import dataclass, field

from shell import contract

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_DIR = os.path.join(ROOT, "games")


@dataclass
class GameEntry:
    folder: str                 # имя папки в games/
    path: str                   # полный путь к папке
    module: object = None
    info: dict = None
    error: str = None           # почему не загрузилась (None - загрузилась)
    warnings: list = field(default_factory=list)

    @property
    def id(self):
        return self.info["id"] if self.info else self.folder

    @property
    def ok(self):
        return self.error is None

    def title(self, lang):
        if not self.info:
            return self.folder
        t = self.info["title"]
        return t.get(lang) or t.get("en") or self.folder

    def summary(self, lang):
        if not self.info:
            return ""
        s = self.info["summary"]
        return s.get(lang) or s.get("en") or ""

    def preview_path(self):
        if not self.info:
            return None
        p = os.path.join(self.path, self.info["preview"])
        return p if os.path.isfile(p) else None

    def speaks(self, lang):
        langs = (self.info or {}).get("langs")
        return langs is None or lang in langs


def _short_error(exc):
    last = traceback.extract_tb(exc.__traceback__)[-1:] if exc.__traceback__ else []
    where = f" ({os.path.basename(last[0].filename)}:{last[0].lineno})" if last else ""
    return f"{type(exc).__name__}: {exc}{where}"


def discover(games_dir=GAMES_DIR):
    """Найти игры. Пакет - имя папки games_dir, её родитель добавляется в sys.path."""
    games_dir = os.path.abspath(games_dir)
    parent, package = os.path.split(games_dir)
    if parent not in sys.path:
        sys.path.insert(0, parent)
    entries = []
    if not os.path.isdir(games_dir):
        return entries
    for name in sorted(os.listdir(games_dir)):
        path = os.path.join(games_dir, name)
        if name.startswith((".", "_")) or not os.path.isfile(os.path.join(path, "__init__.py")):
            continue
        entry = GameEntry(name, path)
        entries.append(entry)
        try:
            module = importlib.import_module(f"{package}.{name}")
        except Exception as e:  # noqa: BLE001 - любая ошибка игры - её запись, не падение оболочки
            entry.error = "не импортируется: " + _short_error(e)
            continue
        findings = contract.check_module(module, path)
        errs = contract.errors(findings)
        entry.warnings = [f for f in findings if f.level != contract.ERROR]
        if errs:
            entry.error = "; ".join(f.text for f in errs)
            continue
        entry.module, entry.info = module, module.GAME_INFO
        if entry.info["id"] != name:          # папка = id: так id уникален сам собой
            entry.error = f"id «{entry.info['id']}» не совпадает с папкой games/{name}"
            entry.info, entry.module = None, None
    return entries
