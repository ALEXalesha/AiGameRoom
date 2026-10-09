"""tools/contract_check.py: исправная игра проходит, каждое нарушение называется понятно -
правило, файл, что не так. Папки игр собираются во временной папке."""
import os
import subprocess
import sys
import textwrap

import pytest

from shell.contract import ERROR, WARN, check_info
from tests.conftest import ROOT
from tools import contract_check

INFO = '''GAME_INFO = {
    "id": "sample",
    "title": {"ru": "Образец", "en": "Sample"},
    "summary": {"ru": "игра для проверки", "en": "a game for the check"},
    "preview": "docs/preview.png",
    "version": "1.0.0",
}
'''

WIDGET = '''

def create_widget(ctx):
    from PySide6.QtWidgets import QLabel
    w = QLabel("sample")
    w.shutdown = lambda: True
    return w
'''


def write(base, rel, text):
    path = os.path.join(base, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(text))


def make_project(base, init=INFO + WIDGET, ci="runs-on: windows"):
    """Полная папка игры по контракту."""
    for rel in ("main.py", "README.md", "README.ru.md", "CHANGELOG.md", "LICENSE", "build.py",
                "installer.nsi", "game/core/__init__.py", "game/ai/__init__.py", "game/ui/__init__.py",
                "tests/test_sample.py"):
        write(base, rel, "\n")
    write(base, "aikit/VERSION", open(os.path.join(ROOT, "aikit", "VERSION"), encoding="utf-8").read())
    write(base, "game/__init__.py", init)
    write(base, ".gitea/workflows/ci.yml", f"jobs:\n  t:\n    {ci}\n")
    write(base, ".github/workflows/ci.yml", "jobs:\n  t:\n    runs-on: windows-latest\n")
    os.makedirs(os.path.join(base, "docs"), exist_ok=True)
    open(os.path.join(base, "docs", "preview.png"), "wb").write(b"\x89PNG\r\n")
    return str(base)


def rules(findings, level=None):
    return {f.rule for f in findings if level is None or f.level == level}


def test_good_project_passes(tmp_path):
    layout, findings = contract_check.check(make_project(tmp_path / "Good"))
    assert layout == "project"
    assert not rules(findings, ERROR), [str(f) for f in findings]


def test_good_project_passes_with_run(tmp_path):
    layout, findings = contract_check.check(make_project(tmp_path / "Good"), run=True)
    assert not rules(findings, ERROR), [str(f) for f in findings]


def test_every_violation_is_named(tmp_path):
    base = make_project(tmp_path / "Bad", ci="runs-on: windows-latest")
    for rel in ("README.ru.md", "LICENSE"):
        os.remove(os.path.join(base, rel))
    write(base, "game/core/rules.py", "from PySide6.QtCore import QObject\n")
    write(base, "game/ui/view.py", "import pygame\nimport torch\nfrom PySide6.QtWidgets import QMainWindow\n\n\nclass W(QMainWindow):\n    pass\n")
    write(base, "game/ai/where.py", 'MODELS = r"C:' + '\\\\Users\\\\somebody\\\\models"\n')
    write(base, "docs/notes.md", "пишите на someone" + "@" + "mail.ru\n")
    _, findings = contract_check.check(base)
    errs = rules(findings, ERROR)
    assert {"ci.gitea", "layout.readme", "layout.license", "code.core_qt", "code.pygame",
            "privacy.path", "privacy.email"} <= errs
    assert {"code.torch", "code.mainwindow"} <= rules(findings, WARN)
    text = contract_check.report(base, "project", findings)
    assert "НЕ соответствует контракту" in text
    assert "[code.pygame] ui/view.py:1: import pygame - только PySide6, без pygame" in text
    assert "[code.core_qt] core/rules.py:1: правила в core/ без Qt" in text
    assert "[ci.gitea]" in text and "windows-latest" in text
    assert "нет README.ru.md" in text


def test_bad_game_info_is_explained():
    out = check_info({"id": "Bad id", "title": {"ru": "x"}, "summary": "строка", "preview": "../p.png",
                      "version": "v1", "langs": ["de"]})
    by = {f.rule: f.text for f in out}
    assert "строчная латиница" in by["info.id"]
    assert "['title']['en']" in [f.text for f in out if f.rule == "info.title"][0]
    assert "словарь" in by["info.summary"]
    assert "без .." in by["info.preview"]
    assert "1.2.3" in by["info.version"]
    assert "langs" in by["info.langs"]
    assert "нет ключей" not in " ".join(by.values())
    assert "нет ключей: summary" in check_info({"id": "a", "title": {"ru": "a", "en": "a"},
                                               "preview": "p.png", "version": "1.0.0"})[0].text


def test_entry_errors_come_from_the_game_process(tmp_path):
    base = make_project(tmp_path / "NoEntry", init='GAME_INFO = {"id": "x"}\n')
    _, findings = contract_check.check(base)
    texts = [str(f) for f in findings]
    assert any("[info.keys]" in t and "title" in t for t in texts)
    assert any("нет функции create_widget(ctx)" in t for t in texts)


def test_import_crash_is_reported(tmp_path):
    base = make_project(tmp_path / "Crash", init="raise RuntimeError('сломано нарочно')\n")
    _, findings = contract_check.check(base)
    assert any(f.rule == "entry.import" and "сломано нарочно" in f.text for f in findings)


def test_run_catches_slow_shutdown_and_files_outside_data_dir(tmp_path):
    widget = '''

def create_widget(ctx):
    import os, time
    from PySide6.QtWidgets import QLabel
    open(os.path.join(os.path.dirname(__file__), "scores.txt"), "w").write("1")
    w = QLabel("x")
    w.shutdown = lambda: time.sleep(2.2) or True
    return w
'''
    base = make_project(tmp_path / "Rude", init=INFO + widget)
    _, findings = contract_check.check(base, run=True)
    by = {f.rule: f.text for f in findings if f.level == ERROR}
    assert "run.files" in by and "scores.txt" in by["run.files"]
    assert "run.shutdown" in by and "больше 2 с" in by["run.shutdown"]


def test_run_catches_create_widget_crash(tmp_path):
    widget = "\n\ndef create_widget(ctx):\n    raise ValueError('нет стола')\n"
    _, findings = contract_check.check(make_project(tmp_path / "Boom", init=INFO + widget), run=True)
    assert any(f.rule == "run.create" and "нет стола" in f.text for f in findings)


def test_not_a_game_folder(tmp_path):
    layout, findings = contract_check.check(str(tmp_path))
    assert layout == "?" and rules(findings) == {"layout.game"}


def test_cli_exit_code_and_output(tmp_path):
    good = make_project(tmp_path / "Good")
    bad = make_project(tmp_path / "Bad", ci="runs-on: ubuntu-latest")
    run = lambda *a: subprocess.run([sys.executable, os.path.join(ROOT, "tools", "contract_check.py"), *a],
                                    capture_output=True, text=True, encoding="utf-8", timeout=180)
    r = run(good)
    assert r.returncode == 0 and "соответствует контракту" in r.stdout
    r = run(good, bad)
    assert r.returncode == 1
    assert "Bad (папка игры)" in r.stdout and "[ci.gitea]" in r.stdout


@pytest.mark.parametrize("folder", ["fixture_games/good", "fixture_games/bad_info"])
def test_vendored_layout(folder):
    layout, findings = contract_check.check(os.path.join(ROOT, "tests", "fixtures", folder))
    assert layout == "vendored"
    assert bool(rules(findings, ERROR)) == folder.endswith("bad_info")
