"""Сборка: версия в двух местах совпадает, игры попадают внутрь, лишнее не удаляется, а
откладывается."""
import os

import build
from shell.version import VERSION
from tests.conftest import ROOT


def test_version_same_in_installer_and_shell():
    assert build.version() == VERSION


def test_no_pygame_no_torch():
    assert "pygame" in build.EXCLUDE and "torch" in build.EXCLUDE
    req = open(os.path.join(ROOT, "requirements.txt"), encoding="utf-8").read().lower()
    assert "pygame" not in req and "torch" not in req


def test_every_game_module_is_a_hidden_import():
    mods = build.game_modules()
    assert "games.durak" in mods and "games.durak.ui.widget" in mods
    assert "games.tictactoe._adapter" in mods and "games.tictactoe.app.app" in mods
    assert not [m for m in mods if ".train" in m]


def test_trim_moves_files_instead_of_deleting(tmp_path):
    qt = tmp_path / "app" / "_internal" / "PySide6"
    (qt / "translations").mkdir(parents=True)
    (qt / "opengl32sw.dll").write_bytes(b"x" * 10)
    (qt / "translations" / "qt_de.qm").write_bytes(b"y" * 5)
    (qt / "translations" / "qt_ru.qm").write_bytes(b"z")
    keep = tmp_path / "trimmed"
    assert build.trim(str(tmp_path / "app"), str(keep)) == 15
    assert (keep / "_internal" / "PySide6" / "opengl32sw.dll").exists()
    assert (qt / "translations" / "qt_ru.qm").exists()


def test_installer_is_per_user_and_russian():
    nsi = open(os.path.join(ROOT, "installer.nsi"), encoding="utf-8").read()
    assert "RequestExecutionLevel user" in nsi and 'MUI_LANGUAGE "Russian"' in nsi
    assert '!define APP "AiGameRoom"' in nsi and r'$APPDATA\${APP}' in nsi


def test_icon_renders(qapp):
    from shell.icon import app_icon, render
    img = render(64)
    assert img.width() == 64 and img.pixelColor(32, 4).alpha() > 0
    assert not app_icon().isNull()


def test_tictactoe_models_are_found_beside_the_copy():
    import games.tictactoe._adapter  # noqa: F401 - подменяет paths.resource_dir
    from games.tictactoe import paths
    assert os.path.isfile(paths.resource("models", "3x3-strong.npz"))
