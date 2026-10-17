"""Проверка папки игры по docs/contract.md.

    python tools/contract_check.py ..\\DurakAiGame          # папка игры (game/ внутри)
    python tools/contract_check.py games\\durak --run       # копия в оболочке + запуск виджета
    python tools/contract_check.py --games --run            # все копии в games/
    python tools/contract_check.py ПАПКА --json             # находки списком для программ

Что проверяется:
- устройство папки: main.py, game/, aikit/VERSION, tests/, README EN/RU, CHANGELOG, LICENSE,
  CI для Gitea (runs-on: windows) и GitHub;
- код: без pygame, правила в game/core без Qt, PyTorch - только по решению Алексея,
  игра не создаёт своё главное окно, нет личного (почта, пути к папкам пользователя);
- графики в статистике (правило автора 10.10): код игры берёт aikit.charts; свой модуль
  графиков (chart.py / charts.py) - предупреждение, графиков нет совсем - ошибка;
- вход: GAME_INFO и create_widget(ctx) - в отдельном процессе, у каждой игры свой `game`;
- с --run: виджет создаётся без экрана, тема и язык меняются на лету, shutdown() за 2 с,
  потоки остановлены, файлы пишутся только в ctx.data_dir.

Код возврата 1, если есть хоть одна ОШИБКА.
"""
import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from shell.contract import ERROR, WARN, Finding, check_module, errors  # noqa: E402

MARK = "@@CONTRACT@@"
TEXT_EXT = (".py", ".md", ".txt", ".json", ".yml", ".yaml", ".ini", ".nsi", ".toml", ".cfg", ".sh")
SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache", ".hypothesis", "build", "dist", ".venv",
             ".ci-venv", "runs", "saves"}
EMAIL_RE = re.compile(r"\b[\w.+-]+@(?!example\.)[\w-]+\.(com|ru|net|org|io|me)\b")
USER_PATH_RE = re.compile(r"\b[A-Za-z]:[\\/]{1,2}(Users|Drive)[\\/]{1,2}(?!<)[\w.-]{3,}", re.IGNORECASE)
ALLOWED_EMAILS = ("noreply@anthropic.com", "noreply@github.com")


def layout_of(path):
    if os.path.isfile(os.path.join(path, "game", "__init__.py")):
        return "project"
    if os.path.isfile(os.path.join(path, "__init__.py")):
        return "vendored"
    return None


def walk_files(top, ext=None):
    for folder, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if ext is None or name.endswith(ext):
                yield os.path.join(folder, name)


# --- устройство папки ---


def check_layout(path):
    out = []

    def need(rel, rule, level=ERROR, what=None):
        if not os.path.exists(os.path.join(path, rel)):
            out.append(Finding(level, rule, f"нет {rel}" + (f" - {what}" if what else "")))
            return False
        return True

    need("main.py", "layout.main", what="отдельный запуск игры")
    need(os.path.join("aikit", "VERSION"), "layout.aikit", what="копия общего aikit")
    tests = os.path.join(path, "tests")
    if not os.path.isdir(tests) or not any(n.startswith("test_") and n.endswith(".py") for n in os.listdir(tests)):
        out.append(Finding(ERROR, "layout.tests", "нет tests/ с test_*.py"))
    for rel in ("README.md", "README.ru.md"):
        need(rel, "layout.readme", what="README на английском и русском")
    need("CHANGELOG.md", "layout.changelog")
    need("LICENSE", "layout.license")
    gitea = os.path.join(".gitea", "workflows", "ci.yml")
    if need(gitea, "ci.gitea", what="проверки на Gitea"):
        text = open(os.path.join(path, gitea), encoding="utf-8", errors="replace").read()
        if not re.search(r"^\s*runs-on:\s*windows\s*$", text, re.MULTILINE):
            out.append(Finding(ERROR, "ci.gitea", f"{gitea}: нужно runs-on: windows (раннер ПК), не windows-latest"))
    need(os.path.join(".github", "workflows", "ci.yml"), "ci.github", what="проверки на GitHub")
    for rel in ("build.py", "installer.nsi"):
        need(rel, "layout.build", WARN, "сборка и установщик")
    for part in ("core", "ai", "ui"):
        need(os.path.join("game", part), "layout.parts", WARN)
    return out


# --- код ---


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield node.lineno, a.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module


def uses_aikit_charts(tree):
    """import aikit.charts / from aikit.charts import ... / from aikit import charts."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.startswith("aikit.charts") for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.startswith("aikit.charts"):
                return True
            if node.module == "aikit" and any(a.name == "charts" for a in node.names):
                return True
    return False


def uses_aikit_skin(tree):
    """import aikit.skin / from aikit.skin import ... / from aikit import skin."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(a.name.startswith("aikit.skin") for a in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.startswith("aikit.skin"):
                return True
            if node.module == "aikit" and any(a.name == "skin" for a in node.names):
                return True
    return False


def check_code(code_root):
    out = []
    core = os.path.join(code_root, "core")
    shared = os.path.join(code_root, "aikit") + os.sep
    charts, local_charts, skin = False, [], False
    for path in walk_files(code_root, ".py"):
        rel = os.path.relpath(path, code_root).replace("\\", "/")
        try:
            tree = ast.parse(open(path, encoding="utf-8").read())
        except (SyntaxError, UnicodeDecodeError) as e:
            out.append(Finding(ERROR, "code.syntax", f"{rel}: не разбирается ({e})"))
            continue
        in_core = os.path.abspath(path).startswith(os.path.abspath(core) + os.sep)
        if not os.path.abspath(path).startswith(os.path.abspath(shared)):
            charts = charts or uses_aikit_charts(tree)
            skin = skin or uses_aikit_skin(tree)
            if os.path.basename(path) in ("chart.py", "charts.py"):
                local_charts.append(rel)
        for line, name in _imports(tree):
            top = name.split(".")[0]
            if top == "pygame":
                out.append(Finding(ERROR, "code.pygame", f"{rel}:{line}: import {name} - только PySide6, без pygame"))
            elif top == "torch":
                out.append(Finding(WARN, "code.torch", f"{rel}:{line}: PyTorch - только по решению Алексея"))
            elif in_core and top in ("PySide6", "PyQt5", "PyQt6"):
                out.append(Finding(ERROR, "code.core_qt", f"{rel}:{line}: правила в core/ без Qt"))
        for node in ast.walk(tree):
            if (isinstance(node, ast.ClassDef) and any(
                    (isinstance(b, ast.Name) and b.id == "QMainWindow")
                    or (isinstance(b, ast.Attribute) and b.attr == "QMainWindow") for b in node.bases)):
                out.append(Finding(WARN, "code.mainwindow",
                                   f"{rel}:{node.lineno}: class {node.name}(QMainWindow) - окно даёт оболочка или run_standalone"))
    if not charts and local_charts:
        out.append(Finding(WARN, "stats.charts", f"графики своим модулем ({', '.join(local_charts)}), "
                                                 "не aikit.charts - перенести на общий"))
    elif not charts:
        out.append(Finding(ERROR, "stats.charts", "в статистике нет графиков: экран статистики строит их "
                                                  "из aikit.charts (доля побед, уровни, длина партии, рекорды)"))
    if not skin:
        out.append(Finding(WARN, "pages.skin", "настройки и статистика общим видом aikit: свой стиль игры - "
                                               "aikit.skin (Skin, SkinPage; правило автора 17.10)"))
    return out


def check_privacy(path):
    out = []
    shared = os.path.join(path, "aikit") + os.sep       # общий набор проверяется в оболочке
    for f in walk_files(path):
        if not f.endswith(TEXT_EXT) or f.startswith(shared):
            continue
        try:
            text = open(f, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError):
            continue
        rel = os.path.relpath(f, path).replace("\\", "/")
        for m in EMAIL_RE.finditer(text):
            if m.group(0).lower() not in ALLOWED_EMAILS:
                out.append(Finding(ERROR, "privacy.email", f"{rel}: почта в файле"))
                break
        if USER_PATH_RE.search(text):
            out.append(Finding(ERROR, "privacy.path", f"{rel}: личный путь к папке на диске"))
    return out


def check_aikit_version(path):
    mine = os.path.join(ROOT, "aikit", "VERSION")
    theirs = os.path.join(path, "aikit", "VERSION")
    try:
        a = open(mine, encoding="utf-8").read().strip()
        b = open(theirs, encoding="utf-8").read().strip()
    except OSError:
        return []
    if a != b:
        return [Finding(WARN, "aikit.version", f"aikit игры {b}, у оболочки {a}: при переносе останется одна версия, улучшения - во все копии")]
    return []


# --- вход игры и запуск: в отдельном процессе ---


def probe(path, layout, run, timeout=180):
    cmd = [sys.executable, os.path.abspath(__file__), "--probe", path, "--layout", layout]
    if run:
        cmd.append("--run")
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1",
               MKL_NUM_THREADS="1", PYTHONIOENCODING="utf-8",
               PYTHONDONTWRITEBYTECODE="1")   # чужую папку не трогаем даже __pycache__
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=timeout, env=env, cwd=tempfile.gettempdir())
    except subprocess.TimeoutExpired:
        return [Finding(ERROR, "probe.timeout", f"проверка входа не уложилась в {timeout} с (зависла?)")]
    for line in r.stdout.splitlines():
        if line.startswith(MARK):
            return [Finding(**d) for d in json.loads(line[len(MARK):])]
    tail = (r.stderr or r.stdout).strip().splitlines()[-6:]
    return [Finding(ERROR, "probe.crash", "проверка входа упала: " + " | ".join(tail))]


def _snapshot(top):
    snap = {}
    for f in walk_files(top):
        try:
            snap[f] = os.path.getmtime(f)
        except OSError:
            pass
    return snap


def child(path, layout, run):
    """Внутри отдельного процесса: импорт игры, проверка входа, по --run - запуск виджета."""
    out = []
    path = os.path.abspath(path)
    if layout == "project":
        sys.path.insert(0, path)
        name = "game"
        root = path
    else:
        parent, folder = os.path.split(path)
        sys.path.insert(0, os.path.dirname(parent))
        sys.path.insert(1, ROOT)
        name = f"{os.path.basename(parent)}.{folder}"
        root = path
    import importlib
    import threading
    try:
        module = importlib.import_module(name)
    except Exception as e:  # noqa: BLE001
        return [Finding(ERROR, "entry.import", f"{name} не импортируется: {type(e).__name__}: {e}")]
    out += check_module(module, root)
    if errors(out) or not run:
        return out
    info = module.GAME_INFO
    if layout == "vendored" and info.get("id") != os.path.basename(path):
        out.append(Finding(ERROR, "info.id", f"id «{info.get('id')}» не совпадает с папкой {os.path.basename(path)}"))

    caught = []
    sys.excepthook = lambda t, v, tb: caught.append(f"{t.__name__}: {v}")
    from aikit import offscreen
    offscreen.setup(force=True)
    from PySide6.QtCore import QCoreApplication, QEvent, QThread
    from PySide6.QtWidgets import QApplication, QWidget

    from aikit.host import Context
    app = QApplication.instance() or QApplication([])
    data = tempfile.mkdtemp(prefix="contract-")
    before = _snapshot(root)
    threads_before = threading.active_count()
    import time
    try:
        ctx = Context(data, "dark", "ru", 0)
        widget = module.create_widget(ctx)
    except Exception as e:  # noqa: BLE001
        return out + [Finding(ERROR, "run.create", f"create_widget(ctx) упала: {type(e).__name__}: {e}")]
    if not isinstance(widget, QWidget):
        return out + [Finding(ERROR, "run.widget", f"create_widget вернула {type(widget).__name__}, а не QWidget")]
    if widget.isWindow() and widget.parent() is None and type(widget).__name__ == "QMainWindow":
        out.append(Finding(WARN, "run.widget", "create_widget вернула главное окно"))
    widget.resize(1180, 780)
    widget.show()
    for _ in range(5):
        app.processEvents()
    ctx.set_theme("light")
    ctx.set_lang("en")
    app.processEvents()
    ctx.set_theme("dark")
    ctx.set_lang("ru")
    app.processEvents()
    widget.grab()
    shutdown = getattr(widget, "shutdown", None)
    if callable(shutdown):
        started = time.perf_counter()
        try:
            result = shutdown()
        except Exception as e:  # noqa: BLE001
            out.append(Finding(ERROR, "run.shutdown", f"shutdown() упала: {type(e).__name__}: {e}"))
            result = None
        spent = time.perf_counter() - started
        if spent > 2.0:
            out.append(Finding(ERROR, "run.shutdown", f"shutdown() шла {spent:.1f} с - больше 2 с"))
        if result is False:
            out.append(Finding(ERROR, "run.shutdown", "shutdown() вернула False: потоки не остановились"))
    else:
        out.append(Finding(WARN, "run.shutdown", "нет shutdown(): при закрытии нечем остановить потоки"))
    running = [t for t in widget.findChildren(QThread) if t.isRunning()]
    if running:
        out.append(Finding(ERROR, "run.threads", f"после shutdown() работают QThread: {len(running)}"))
    widget.close()
    widget.deleteLater()
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    deadline = time.perf_counter() + 2.0
    while threading.active_count() > threads_before and time.perf_counter() < deadline:
        time.sleep(0.05)
    if threading.active_count() > threads_before:
        extra = [t.name for t in threading.enumerate()][threads_before:]
        out.append(Finding(ERROR, "run.threads", f"после закрытия живы потоки Python: {', '.join(extra)}"))
    after = _snapshot(root)
    touched = sorted(os.path.relpath(f, root) for f, m in after.items() if before.get(f) != m)
    if touched:
        out.append(Finding(ERROR, "run.files", "игра писала в свою папку, а не в ctx.data_dir: " + ", ".join(touched[:5])))
    for c in caught:
        out.append(Finding(ERROR, "run.exception", f"исключение в окне игры: {c}"))
    return out


# --- сборка отчёта ---


def check(path, run=False):
    """Все находки по папке игры."""
    path = os.path.abspath(path)
    layout = layout_of(path)
    if layout is None:
        return "?", [Finding(ERROR, "layout.game", "нет game/__init__.py (папка игры) и __init__.py (копия в games/)")]
    out = []
    if layout == "project":
        out += check_layout(path)
        out += check_code(os.path.join(path, "game"))
        out += check_aikit_version(path)
    else:
        out += check_code(path)
    out += check_privacy(path)
    out += probe(path, layout, run)
    return layout, out


def report(path, layout, findings):
    kind = {"project": "папка игры", "vendored": "копия в оболочке"}.get(layout, "?")
    lines = [f"{os.path.basename(os.path.abspath(path))} ({kind})"]
    for f in sorted(findings, key=lambda f: (f.level != ERROR, f.rule)):
        lines.append("  " + str(f))
    n_err = len(errors(findings))
    n_warn = len(findings) - n_err
    verdict = "соответствует контракту" if not n_err else "НЕ соответствует контракту"
    lines.append(f"  итог: ошибок {n_err}, предупреждений {n_warn} - {verdict}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Проверка игры по docs/contract.md")
    ap.add_argument("paths", nargs="*", help="папки игр")
    ap.add_argument("--games", action="store_true", help="все копии в games/")
    ap.add_argument("--run", action="store_true", help="ещё и создать виджет без экрана")
    ap.add_argument("--json", action="store_true", help="находки в JSON")
    ap.add_argument("--probe", help=argparse.SUPPRESS)
    ap.add_argument("--layout", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")      # в канал - UTF-8; в консоль Python пишет сам
    if args.probe:
        findings = child(args.probe, args.layout, args.run)
        sys.stdout.write("\n" + MARK + json.dumps([f.__dict__ for f in findings], ensure_ascii=False) + "\n")
        sys.stdout.flush()
        os._exit(0)         # без разборки Qt и потоков игры: итог уже записан
    paths = list(args.paths)
    if args.games:
        games = os.path.join(ROOT, "games")
        paths += [os.path.join(games, n) for n in sorted(os.listdir(games))
                  if not n.startswith((".", "_")) and os.path.isfile(os.path.join(games, n, "__init__.py"))]
    if not paths:
        ap.error("укажите папку игры или --games")
    code, results = 0, []
    for p in paths:
        layout, findings = check(p, args.run)
        code |= bool(errors(findings))
        results.append({"path": os.path.basename(os.path.abspath(p)), "layout": layout,
                        "findings": [f.__dict__ for f in findings]})
        if not args.json:
            print(report(p, layout, findings), flush=True)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=1))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
