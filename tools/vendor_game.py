"""Копия игры в games/<id>/ - так игры попадают в оболочку.

    python tools/vendor_game.py durak              # одну игру из соседней папки (games/vendor.json)
    python tools/vendor_game.py --all              # все игры из списка
    python tools/vendor_game.py durak --src ПАПКА  # из другой папки

Папка игры не меняется: берётся копия. Каждая игра у себя зовёт свой пакет `game`, а в одной
программе два пакета `game` не уживаются. Поэтому при копировании импорты переписываются:
`from game.ai import x` -> `from games.durak.ai import x`. Переписываются только операторы
import (по дереву разбора), строки и комментарии не трогаются.

Раскладки (games/vendor.json):
- contract - игра по contract.md: game/ целиком становится games/<id>/, рядом кладётся
  превью из GAME_INFO["preview"];
- legacy - игра до контракта (TicTacToeAi): папки и модули из "map" переезжают внутрь
  games/<id>/, "copy" копируется как есть, "keep" - файлы оболочки (переходник), которые
  остаются от прежней копии.

Прежняя копия уходит в Корзину, насовсем ничего не удаляется. Откуда и с какого коммита
взята копия - в games/<id>/VENDOR.json (только имя папки, без полных путей).
"""
import argparse
import ast
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools.trash import to_recycle_bin  # noqa: E402

SKIP_DIRS = {"__pycache__", ".pytest_cache", ".hypothesis"}
SKIP_EXT = (".pyc", ".pyo")


class VendorError(Exception):
    pass


# --- переписывание импортов ---


def _target(package, mapping, dotted):
    """Новое имя модуля для 'game.ai.x' или None, если модуль не из игры."""
    parts = dotted.split(".")
    if parts[0] not in mapping:
        return None
    sub = mapping[parts[0]]
    return ".".join(p for p in [package, sub, *parts[1:]] if p)


def rewrite_imports(text, mapping, package):
    """Вернуть (новый текст, [проблемы]). mapping: {старое имя верхнего уровня: путь внутри
    пакета игры, '' - сам пакет}. Проблема - импорт, который нельзя переписать без изменения
    смысла (import game.x, import os, paths): такой файл копировать нельзя."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return text, [f"не разбирается: {e}"]
    lines = text.splitlines(keepends=True)
    edits = []          # (строка, столбец, старый кусок по регулярке, новый)
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            new = _target(package, mapping, node.module)
            if new is not None:
                edits.append((node.lineno - 1, node.col_offset,
                              r"from\s+" + re.escape(node.module) + r"\b", "from " + new))
        elif isinstance(node, ast.Import):
            hits = [a for a in node.names if a.name.split(".")[0] in mapping]
            if not hits:
                continue
            if len(node.names) != 1:
                problems.append(f"строка {node.lineno}: несколько модулей в одном import")
                continue
            alias = node.names[0]
            if "." in alias.name:
                problems.append(f"строка {node.lineno}: import {alias.name} - замените на from ... import")
                continue
            sub = mapping[alias.name]
            bound = alias.asname or alias.name
            if sub:
                parent, _, leaf = ".".join(p for p in (package, sub) if p).rpartition(".")
                new = f"from {parent} import {leaf}" + (f" as {bound}" if bound != leaf else "")
            else:
                new = f"import {package} as {bound}"
            stmt = r"import\s+" + re.escape(alias.name) + (r"\s+as\s+" + re.escape(alias.asname) if alias.asname else "") + r"\b"
            edits.append((node.lineno - 1, node.col_offset, stmt, new))
    for row, col, pattern, new in sorted(edits, reverse=True):
        line = lines[row]
        head, tail = line[:col], line[col:]
        changed, n = re.subn("^" + pattern, new, tail, count=1)
        if n != 1:
            problems.append(f"строка {row + 1}: не получилось переписать «{line.strip()}»")
            continue
        lines[row] = head + changed
    out = "".join(lines)
    problems += leftover_imports(out, mapping)
    return out, problems


def leftover_imports(text, mapping):
    """Импорты старых имён, оставшиеся после переписывания (проверка самого переписывания)."""
    try:
        tree = ast.parse(text)
    except SyntaxError as e:
        return [f"после переписывания не разбирается: {e}"]
    left = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.split(".")[0] in mapping:
                left.append(f"строка {node.lineno}: остался from {node.module}")
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in mapping:
                    left.append(f"строка {node.lineno}: остался import {a.name}")
    return left


def module_strings(text, mapping):
    """Строки вида 'game.train.selfplay' - имя модуля в строке (multiprocessing, -m).
    Их переписывать вслепую опасно, поэтому только предупреждение."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            m = re.fullmatch(r"([A-Za-z_]\w*)(\.[A-Za-z_]\w*)+", node.value)
            if m and m.group(1) in mapping:
                found.append(f"строка {node.lineno}: '{node.value}'")
    return found


# --- копирование ---


def _copy_tree(src, dst):
    def ignore(_dir, names):
        return [n for n in names if n in SKIP_DIRS or n.endswith(SKIP_EXT)]
    if os.path.isdir(src):
        shutil.copytree(src, dst, ignore=ignore)
    else:
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)


def _git(src, *args):
    try:
        r = subprocess.run(["git", "-C", src, *args], capture_output=True, text=True, timeout=30)
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def preview_of(src):
    """GAME_INFO['preview'] из game/__init__.py - по дереву разбора, без импорта игры."""
    path = os.path.join(src, "game", "__init__.py")
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "GAME_INFO" for t in node.targets):
            if isinstance(node.value, ast.Dict):
                for k, v in zip(node.value.keys, node.value.values):
                    if isinstance(k, ast.Constant) and k.value == "preview" and isinstance(v, ast.Constant):
                        return v.value
    return None


def plan_copies(game_id, entry, src):
    """[(откуда, куда внутри games/<id>)] и {старое имя: путь внутри пакета}."""
    layout = entry.get("layout", "contract")
    if layout == "contract":
        if not os.path.isfile(os.path.join(src, "game", "__init__.py")):
            raise VendorError(f"{src}: нет game/__init__.py - это не игра по контракту")
        copies = [(os.path.join(src, "game"), "")]
        preview = preview_of(src)
        if preview and os.path.isfile(os.path.join(src, preview)):
            copies.append((os.path.join(src, preview), preview))
        return copies, {"game": ""}
    if layout == "legacy":
        mapping = dict(entry["map"])
        copies = []
        for old, new in mapping.items():
            for cand in (os.path.join(src, old), os.path.join(src, old + ".py")):
                if os.path.exists(cand):
                    copies.append((cand, new + (".py" if cand.endswith(".py") else "")))
                    break
            else:
                raise VendorError(f"{src}: нет {old} из map")
        for rel in entry.get("copy", []):
            if not os.path.exists(os.path.join(src, rel)):
                raise VendorError(f"{src}: нет {rel} из copy")
            copies.append((os.path.join(src, rel), rel))
        return copies, mapping
    raise VendorError(f"{game_id}: неизвестная раскладка {layout}")


def vendor(game_id, entry, src, games_dir, package=None, today=None):
    """Собрать копию игры в games_dir/<game_id>. Вернуть отчёт {файлы, предупреждения}."""
    package = package or f"{os.path.basename(os.path.normpath(games_dir))}.{game_id}"
    src = os.path.abspath(src)
    copies, mapping = plan_copies(game_id, entry, src)
    dest = os.path.join(games_dir, game_id)
    tmp = os.path.join(games_dir, f".vendor-{game_id}")
    if os.path.exists(tmp):
        to_recycle_bin(tmp)
    os.makedirs(tmp)
    try:
        for s, rel in copies:
            if rel:
                _copy_tree(s, os.path.join(tmp, rel))
            else:
                _copy_into(s, tmp)
        warnings, problems, count = [], [], 0
        for folder, _dirs, files in os.walk(tmp):
            for name in files:
                if not name.endswith(".py"):
                    continue
                path = os.path.join(folder, name)
                rel = os.path.relpath(path, tmp)
                text = open(path, encoding="utf-8").read()
                new, probs = rewrite_imports(text, mapping, package)
                problems += [f"{rel}: {p}" for p in probs]
                warnings += [f"{rel}: имя модуля строкой {w}" for w in module_strings(new, mapping)]
                if new != text:
                    with open(path, "w", encoding="utf-8", newline="") as f:
                        f.write(new)
                count += 1
        if problems:
            raise VendorError("импорты не переписаны:\n  " + "\n  ".join(problems))
        for rel in entry.get("keep", []):
            old = os.path.join(dest, rel)
            if os.path.isfile(old):
                os.makedirs(os.path.dirname(os.path.join(tmp, rel)), exist_ok=True)
                shutil.copy2(old, os.path.join(tmp, rel))
        if not os.path.isfile(os.path.join(tmp, "__init__.py")):
            raise VendorError(f"{game_id}: в копии нет __init__.py (для legacy - переходник в keep)")
        aikit_version = ""
        try:
            aikit_version = open(os.path.join(src, "aikit", "VERSION"), encoding="utf-8").read().strip()
        except OSError:
            pass
        info = {
            "id": game_id,
            "source": os.path.basename(src),
            "layout": entry.get("layout", "contract"),
            "commit": _git(src, "rev-parse", "--short", "HEAD"),
            "uncommitted": bool(_git(src, "status", "--porcelain")),
            "aikit": aikit_version,
            "date": (today or datetime.date.today()).isoformat(),
        }
        with open(os.path.join(tmp, "VENDOR.json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(info, f, ensure_ascii=False, indent=1)
            f.write("\n")
    except BaseException:
        to_recycle_bin(tmp)
        raise
    if os.path.exists(dest):
        to_recycle_bin(dest)
    os.replace(tmp, dest)
    return {"files": count, "warnings": warnings, "info": info}


def _copy_into(src_dir, dst_dir):
    """Содержимое src_dir прямо в dst_dir (game/ -> games/<id>/)."""
    for name in os.listdir(src_dir):
        if name in SKIP_DIRS or name.endswith(SKIP_EXT):
            continue
        _copy_tree(os.path.join(src_dir, name), os.path.join(dst_dir, name))


def load_config(games_dir):
    with open(os.path.join(games_dir, "vendor.json"), encoding="utf-8") as f:
        return json.load(f)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Копия игры в games/<id>/ с переписанными импортами")
    ap.add_argument("ids", nargs="*", help="id игр из games/vendor.json")
    ap.add_argument("--all", action="store_true", help="все игры из списка")
    ap.add_argument("--src", help="папка игры (по умолчанию - соседняя папка из vendor.json)")
    args = ap.parse_args(argv)
    games_dir = os.path.join(ROOT, "games")
    config = load_config(games_dir)
    ids = list(config) if args.all else args.ids
    if not ids:
        ap.error("укажите id игры или --all")
    if args.src and len(ids) != 1:
        ap.error("--src - только для одной игры")
    code = 0
    for game_id in ids:
        if game_id not in config:
            print(f"{game_id}: нет в games/vendor.json")
            code = 1
            continue
        entry = config[game_id]
        src = args.src or os.path.join(os.path.dirname(ROOT), entry["source"])
        try:
            report = vendor(game_id, entry, src, games_dir)
        except (VendorError, OSError) as e:
            print(f"{game_id}: ОШИБКА {e}")
            code = 1
            continue
        info = report["info"]
        dirty = ", есть незакоммиченное" if info["uncommitted"] else ""
        print(f"{game_id}: {report['files']} файлов .py из {info['source']} @ {info['commit'] or '?'}{dirty}")
        for w in report["warnings"]:
            print(f"  внимание: {w}")
    return code


if __name__ == "__main__":
    sys.exit(main())
