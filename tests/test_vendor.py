"""tools/vendor_game.py: импорты переписываются точно, копия собирается из папки игры,
переходник legacy-игры переживает новую копию, в games/ не осталось чужих `game`."""
import json
import os

import pytest

from tests.conftest import ROOT
from tools.vendor_game import (VendorError, leftover_imports, load_config, module_strings,
                               rewrite_imports, vendor)

GAME = {"game": ""}


def rw(text, mapping=GAME, package="games.durak"):
    out, problems = rewrite_imports(text, mapping, package)
    assert not problems, problems
    return out


def test_from_imports_are_rewritten():
    assert rw("from game.ai.search import SearchAgent\n") == "from games.durak.ai.search import SearchAgent\n"
    assert rw("from game import APP_NAME, GAME_INFO\n") == "from games.durak import APP_NAME, GAME_INFO\n"
    assert rw("import game\n") == "import games.durak as game\n"


def test_lazy_and_multiline_imports_keep_indentation():
    src = "def f():\n    from game.core import (\n        cards,\n    )\n    return cards\n"
    assert rw(src) == "def f():\n    from games.durak.core import (\n        cards,\n    )\n    return cards\n"


def test_other_modules_and_lookalikes_are_untouched():
    src = ("from gamepad import x\nimport games_extra\nfrom aikit.game import y\n"
           "s = 'from game.ai import z'\n# from game.ai import w\nfrom . import game\n")
    assert rw(src) == src


def test_legacy_mapping():
    m = {"game": "app", "core": "core", "paths": "paths", "nn": "nn"}
    src = "import paths\nimport paths as p\nfrom core import rules\nfrom game import models\nfrom nn.layers import Dense\n"
    assert rw(src, m, "games.tictactoe") == (
        "from games.tictactoe import paths\nfrom games.tictactoe import paths as p\n"
        "from games.tictactoe.core import rules\nfrom games.tictactoe.app import models\n"
        "from games.tictactoe.nn.layers import Dense\n")


def test_unsafe_imports_are_problems_not_silent():
    _, problems = rewrite_imports("import game.ai\n", GAME, "games.x")
    assert problems and "from ... import" in problems[0]
    _, problems = rewrite_imports("import os, paths\n", {"paths": "paths"}, "games.x")
    assert problems and "несколько модулей" in problems[0]


def test_leftovers_and_module_strings_are_found():
    assert leftover_imports("from game.x import y\n", GAME)
    assert module_strings("TARGET = 'game.train.selfplay'\n", GAME) == ["строка 1: 'game.train.selfplay'"]
    assert module_strings('"""python -m game.train"""\n', GAME) == []


def make_source(base):
    for rel, text in {
        "game/__init__.py": 'from game.version import VERSION\nGAME_INFO = {"id": "toy", "preview": "docs/p.png"}\n',
        "game/version.py": 'VERSION = "1.0.0"\n',
        "game/ui/w.py": "def make():\n    from game.version import VERSION\n    return VERSION\n",
        "game/__pycache__/junk.pyc": "x",
        "docs/p.png": "png",
        "aikit/VERSION": "0.1.0\n",
    }.items():
        path = os.path.join(base, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, "w", encoding="utf-8").write(text)
    return str(base)


def set_aside(tmp_path):
    """Вместо Корзины - в соседнюю папку теста: прогон тестов не засоряет Корзину."""
    def discard(path):
        os.replace(path, tmp_path / f"discarded-{len(os.listdir(tmp_path))}")
    return discard


def test_vendor_contract_layout(tmp_path):
    src = make_source(tmp_path / "ToyGame")
    games = tmp_path / "pkg"
    games.mkdir()
    report = vendor("toy", {"layout": "contract"}, src, str(games), discard=set_aside(tmp_path))
    dest = games / "toy"
    assert report["files"] == 3
    assert (dest / "__init__.py").read_text(encoding="utf-8").startswith("from pkg.toy.version import VERSION")
    assert "from pkg.toy.version import" in (dest / "ui" / "w.py").read_text(encoding="utf-8")
    assert (dest / "docs" / "p.png").exists()
    assert not (dest / "__pycache__").exists()
    info = json.loads((dest / "VENDOR.json").read_text(encoding="utf-8"))
    assert info["source"] == "ToyGame" and info["aikit"] == "0.1.0"
    assert ":" not in info["source"] and os.sep not in info["source"]      # без полных путей


def test_vendor_legacy_keeps_adapter(tmp_path):
    src = tmp_path / "Old"
    for rel, text in {"game/__init__.py": "", "game/app.py": "import paths\nfrom core import rules\n",
                      "core/__init__.py": "", "core/rules.py": "X = 1\n", "paths.py": "P = 1\n",
                      "models/m.json": "{}"}.items():
        os.makedirs(os.path.dirname(src / rel), exist_ok=True)
        (src / rel).write_text(text, encoding="utf-8")
    games = tmp_path / "pkg"
    (games / "old").mkdir(parents=True)
    (games / "old" / "__init__.py").write_text("# переходник\n", encoding="utf-8")
    entry = {"layout": "legacy", "map": {"game": "app", "core": "core", "paths": "paths"},
             "copy": ["models"], "keep": ["__init__.py"]}
    vendor("old", entry, str(src), str(games), discard=set_aside(tmp_path))
    dest = games / "old"
    assert (dest / "__init__.py").read_text(encoding="utf-8") == "# переходник\n"
    assert (dest / "app" / "app.py").read_text(encoding="utf-8") == (
        "from pkg.old import paths\nfrom pkg.old.core import rules\n")
    assert (dest / "models" / "m.json").exists() and (dest / "paths.py").exists()


def test_vendor_refuses_non_contract_folder(tmp_path):
    with pytest.raises(VendorError, match="не игра по контракту"):
        vendor("x", {"layout": "contract"}, str(tmp_path), str(tmp_path), discard=set_aside(tmp_path))


def test_vendored_games_have_no_foreign_imports():
    """Копии в games/ не правились руками мимо инструмента: старых `game` нигде нет."""
    config = load_config(os.path.join(ROOT, "games"))
    for game_id, entry in config.items():
        mapping = entry.get("map", {"game": ""})
        folder = os.path.join(ROOT, "games", game_id)
        assert os.path.isfile(os.path.join(folder, "VENDOR.json")), game_id
        for d, dirs, files in os.walk(folder):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                if f.endswith(".py"):
                    text = open(os.path.join(d, f), encoding="utf-8").read()
                    assert not leftover_imports(text, mapping), (game_id, f)
