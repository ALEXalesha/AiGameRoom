"""Закон оболочки для настоящих игр в games/: каждая открывается и закрывается без ошибок
и без утечек - виджеты удалены, потоки остановлены, память после нескольких кругов не
растёт. Плюс каждая проходит проверку контракта (вход и код)."""
import os
import threading
import time
import tracemalloc

import pytest

from shell import registry
from tests.conftest import ROOT, flush, wait_until

ENTRIES = registry.discover()
GAME_IDS = [e.folder for e in ENTRIES]


def test_games_are_registered():
    assert {"durak", "tictactoe"} <= set(GAME_IDS)
    bad = {e.folder: e.error for e in ENTRIES if not e.ok}
    assert not bad, bad


@pytest.fixture
def shell(make_shell):
    return make_shell()


@pytest.mark.parametrize("game_id", GAME_IDS)
def test_game_opens_and_closes_without_leaks(game_id, shell, qapp, caught):
    from PySide6.QtCore import QThread
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid
    flush(qapp)
    widgets = len(QApplication.allWidgets())
    threads = threading.active_count()
    tab = shell.open_game(game_id)
    assert tab is not None, shell.entries
    game, ctx = tab.game, tab.ctx
    flush(qapp)
    for theme, lang in (("light", "en"), ("dark", "ru")):
        shell.set_theme(theme)
        shell.set_lang(lang)
        qapp.processEvents()
    shell.tabs.setCurrentIndex(0)
    assert tab.paused
    shell.tabs.setCurrentWidget(tab)
    assert not tab.paused
    assert not game.grab().isNull()
    qthreads = game.findChildren(QThread)
    seconds = shell.close_game(tab)
    assert seconds < 2.0
    assert not [t for t in qthreads if isValid(t) and t.isRunning()]
    flush(qapp)
    assert not isValid(game) and not isValid(ctx)
    assert len(QApplication.allWidgets()) == widgets
    assert wait_until(qapp, lambda: threading.active_count() <= threads, 2.0), threading.enumerate()
    assert not shell.problems, shell.problems
    assert not caught, caught


@pytest.mark.parametrize("game_id", GAME_IDS)
def test_memory_returns_after_repeated_open_close(game_id, shell, qapp):
    """Первый круг загружает модели и кэши, дальше каждый круг возвращает память."""
    def cycle():
        shell.close_game(shell.open_game(game_id))
        flush(qapp)
    cycle()
    tracemalloc.start()
    try:
        cycle()
        base = tracemalloc.get_traced_memory()[0]
        for _ in range(4):
            cycle()
        grown = tracemalloc.get_traced_memory()[0] - base
    finally:
        tracemalloc.stop()
    assert grown < 1_500_000, f"{game_id}: +{grown / 1e6:.1f} МБ за 4 круга"


@pytest.mark.parametrize("game_id", GAME_IDS)
def test_game_writes_only_into_its_data_dir(game_id, shell, qapp):
    folder = os.path.join(ROOT, "games", game_id)

    def snapshot():
        out = {}
        for d, dirs, files in os.walk(folder):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                out[os.path.join(d, f)] = os.path.getmtime(os.path.join(d, f))
        return out
    before = snapshot()
    tab = shell.open_game(game_id)
    flush(qapp)
    shell.close_game(tab)
    assert snapshot() == before
    assert os.listdir(os.path.join(shell.root, game_id))


def test_durak_closes_while_ai_plays(shell, qapp):
    """Партия ИИ против ИИ идёт в потоках поиска; закрытие вкладки посреди неё."""
    from PySide6.QtCore import QThread
    tab = shell.open_game("durak")
    game = tab.game
    game.change("mode", "demo")
    game.change("delay_ms", 0)
    game.start_game(seed=7)
    assert wait_until(qapp, lambda: any(t.isRunning() for t in game.findChildren(QThread)), 5.0)
    started = time.perf_counter()
    seconds = shell.close_game(tab)
    assert seconds < 2.0 and time.perf_counter() - started < 2.5
    flush(qapp)
    assert not shell.problems, shell.problems


def test_durak_pause_stops_demo_game(shell, qapp):
    tab = shell.open_game("durak")
    game = tab.game
    game.change("mode", "demo")
    game.change("delay_ms", 0)
    game.change("anim_ms", 0)
    game.start_game(seed=3)
    s = game.session
    assert wait_until(qapp, lambda: len(s.moves) >= 3, 10.0)
    shell.tabs.setCurrentIndex(0)                 # спрятали - партия ИИ против ИИ стоит
    assert tab.paused and not game.timer.isActive()
    assert game.hidden                            # оболочка позвала pause() самого Дурака (1.0.0)
    for _ in range(40):                           # дожидаемся хода, что уже считался в потоке
        qapp.processEvents()
        time.sleep(0.01)
    game.after_change()                           # как будто пришёл ответ ИИ: игра снова заводит таймер
    frozen = len(s.moves)
    for _ in range(40):
        qapp.processEvents()
        time.sleep(0.01)
    assert len(s.moves) == frozen
    shell.tabs.setCurrentWidget(tab)
    assert not tab.paused and not game.hidden
    assert wait_until(qapp, lambda: len(s.moves) > frozen or s.over, 10.0)


def test_tictactoe_net_moves_after_resume(shell, qapp):
    import numpy as np
    tab = shell.open_game("tictactoe")
    inner = tab.game.inner
    inner.change_setting("delay_ms", 0)
    inner.start_play()
    page = inner.game
    page.set_first("net")                     # ход сети ждёт в таймере
    shell.tabs.setCurrentIndex(0)             # спрятали раньше, чем он сработал
    for _ in range(20):
        qapp.processEvents()
    assert np.count_nonzero(page.session.board) == 0
    shell.tabs.setCurrentWidget(tab)
    assert wait_until(qapp, lambda: np.count_nonzero(page.session.board) == 1, 3.0)


def test_tictactoe_theme_from_its_settings_reaches_shell(shell):
    tab = shell.open_game("tictactoe")
    tab.game.inner.change_setting("theme", "light")
    assert shell.theme == "light" and tab.ctx.theme == "light"
    shell.set_theme("dark")
    assert tab.game.inner.settings.theme == "dark"


@pytest.mark.parametrize("game_id", GAME_IDS)
def test_vendored_game_passes_contract_check(game_id):
    from shell.contract import errors
    from tools.contract_check import check
    layout, findings = check(os.path.join(ROOT, "games", game_id))
    assert layout == "vendored"
    assert not errors(findings), [str(f) for f in findings]
