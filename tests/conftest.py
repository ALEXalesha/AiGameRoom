import gc
import os
import sys

for var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(var, "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
FIXTURE_GAMES = os.path.join(ROOT, "tests", "fixtures", "fixture_games")

from aikit import offscreen  # noqa: E402

offscreen.setup(force=True)          # без экрана: никаких видимых окон и захвата мыши

import pytest  # noqa: E402


@pytest.fixture
def qapp():
    """Одно QApplication на весь прогон: второе Qt создать не даст."""
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])


def flush(app):
    """Отработать события и отложенные удаления (deleteLater) - processEvents их не делает."""
    from PySide6.QtCore import QCoreApplication, QEvent
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def wait_until(app, cond, timeout=3.0):
    """Ждать условия с тайм-аутом, не дольше timeout секунд."""
    import time
    deadline = time.perf_counter() + timeout
    while not cond():
        if time.perf_counter() > deadline:
            return False
        app.processEvents()
        time.sleep(0.005)
    return True


@pytest.fixture
def caught():
    """Исключения в слотах Qt идут в sys.excepthook, а не в тест - собираем их."""
    errors = []
    old = sys.excepthook
    sys.excepthook = lambda t, v, tb: errors.append(f"{t.__name__}: {v}")
    yield errors
    sys.excepthook = old


@pytest.fixture
def make_shell(qapp, tmp_path):
    """make_shell(games_dir=...) - окно оболочки с данными во временной папке."""
    from shell.window import ShellWindow
    made = []

    def make(games_dir=None, root=None, place=True):
        kw = {"root": str(root or tmp_path / "home")}
        if games_dir:
            kw["games_dir"] = games_dir
        w = ShellWindow(**kw)
        if place:
            w.resize(1240, 820)
        w.show()
        qapp.processEvents()
        made.append(w)
        return w

    yield make
    for w in made:
        try:
            w.close()
        except RuntimeError:
            pass
    flush(qapp)
