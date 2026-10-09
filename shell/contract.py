"""Проверка входа игры по docs/contract.md: GAME_INFO и create_widget(ctx).

Общая для оболочки (сломанная игра показывается «не загрузилась» с причиной) и для
tools/contract_check.py (проверка любой папки игры). Без Qt.

Находка - Finding(уровень, правило, текст). ERROR - контракт нарушен, игру не открыть;
WARN - открыть можно, но поправить надо.
"""
import inspect
import os
import re
from dataclasses import dataclass

ERROR = "ERROR"
WARN = "WARN"

LANGS = ("ru", "en")
ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+([.-][0-9A-Za-z.-]+)?$")
REQUIRED_KEYS = ("id", "title", "summary", "preview", "version")


@dataclass(frozen=True)
class Finding:
    level: str
    rule: str
    text: str

    def __str__(self):
        mark = "ОШИБКА" if self.level == ERROR else "ВНИМАНИЕ"
        return f"{mark:9} [{self.rule}] {self.text}"


def errors(findings):
    return [f for f in findings if f.level == ERROR]


def _lang_dict(info, key):
    value = info.get(key)
    if not isinstance(value, dict):
        return [Finding(ERROR, f"info.{key}", f"GAME_INFO['{key}'] - словарь {{'ru': ..., 'en': ...}}, а не {type(value).__name__}")]
    out = []
    for lang in LANGS:
        text = value.get(lang)
        if not isinstance(text, str) or not text.strip():
            out.append(Finding(ERROR, f"info.{key}", f"GAME_INFO['{key}']['{lang}'] пустое или не строка"))
    return out


def check_info(info, root=None):
    """Проверить GAME_INFO. root - папка, от которой считается путь превью (None - не
    проверять наличие файла)."""
    if not isinstance(info, dict):
        return [Finding(ERROR, "info", f"GAME_INFO - словарь, а не {type(info).__name__}")]
    out = []
    missing = [k for k in REQUIRED_KEYS if k not in info]
    if missing:
        out.append(Finding(ERROR, "info.keys", "в GAME_INFO нет ключей: " + ", ".join(missing)))
    gid = info.get("id")
    if "id" in info and (not isinstance(gid, str) or not ID_RE.match(gid)):
        out.append(Finding(ERROR, "info.id", f"id {gid!r}: только строчная латиница, цифры и _, с буквы"))
    for key in ("title", "summary"):
        if key in info:
            out += _lang_dict(info, key)
    version = info.get("version")
    if "version" in info and (not isinstance(version, str) or not VERSION_RE.match(version)):
        out.append(Finding(ERROR, "info.version", f"version {version!r}: нужен вид 1.2.3"))
    preview = info.get("preview")
    if "preview" in info:
        if not isinstance(preview, str) or not preview:
            out.append(Finding(ERROR, "info.preview", "preview - относительный путь к картинке"))
        elif os.path.isabs(preview) or ".." in re.split(r"[\\/]", preview):
            out.append(Finding(ERROR, "info.preview", f"preview {preview!r}: путь внутри папки игры, без .. и диска"))
        elif root is not None and not os.path.isfile(os.path.join(root, preview)):
            out.append(Finding(WARN, "info.preview", f"нет файла превью {preview}"))
    langs = info.get("langs")
    if langs is not None and (not isinstance(langs, (list, tuple)) or not langs
                              or any(x not in LANGS for x in langs)):
        out.append(Finding(ERROR, "info.langs", f"langs {langs!r}: список из {', '.join(LANGS)}"))
    return out


def check_entry(create_widget):
    """create_widget(ctx): вызываемая с одним обязательным параметром."""
    if create_widget is None:
        return [Finding(ERROR, "entry.create_widget", "нет функции create_widget(ctx)")]
    if not callable(create_widget):
        return [Finding(ERROR, "entry.create_widget", "create_widget - не функция")]
    try:
        sig = inspect.signature(create_widget)
    except (TypeError, ValueError):
        return []
    params = [p for p in sig.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
    required = [p for p in params if p.default is p.empty]
    if len(required) > 1 or not params:
        return [Finding(ERROR, "entry.create_widget",
                        f"create_widget{sig}: нужен ровно один параметр ctx")]
    return []


def check_module(module, root=None):
    """GAME_INFO и create_widget модуля игры."""
    info = getattr(module, "GAME_INFO", None)
    if info is None:
        out = [Finding(ERROR, "info", "нет GAME_INFO")]
    else:
        out = check_info(info, root)
    return out + check_entry(getattr(module, "create_widget", None))
