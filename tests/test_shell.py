"""Оболочка на играх-образцах (tests/fixtures/fixture_games): список, вкладки, пауза,
закрытие, общие тема и язык, место окна. Всё без экрана."""
import json
import os
import time

import pytest

from tests.conftest import FIXTURE_GAMES, flush, wait_until


@pytest.fixture
def shell(make_shell):
    return make_shell(FIXTURE_GAMES)


def card(shell, game_id):
    return next(c for c in shell.home.cards if c.entry.id == game_id)


def test_registry_keeps_broken_games_with_reason(shell):
    by = {e.folder: e for e in shell.entries}
    assert by["good"].ok and by["hooks"].ok and by["boom"].ok
    assert "не импортируется" in by["broken_import"].error and "нет модуля правил" in by["broken_import"].error
    err = by["bad_info"].error
    assert "summary" in err and "id" in err and "['title']['en']" in err and "1.2.3" in err
    assert "один параметр" in err
    assert "не совпадает с папкой" in by["wrong_id"].error


def test_cards_show_broken_games_without_play_button(shell, qapp):
    flush(qapp)
    broken = card(shell, "broken_import")
    assert broken.objectName() == "gameCardBroken"
    assert broken.play.isHidden()
    assert not broken.error.isHidden() and "нет модуля правил" in broken.error.text()
    good = card(shell, "good")
    assert not good.play.isHidden() and good.error.isHidden()
    assert good.preview.pixmap() is not None and not good.preview.pixmap().isNull()
    assert shell.home.count.text().endswith("3")      # загрузились: good, hooks, boom


def test_home_tab_cannot_be_closed(shell):
    from PySide6.QtWidgets import QTabBar
    bar = shell.tabs.tabBar()
    assert bar.tabButton(0, QTabBar.ButtonPosition.RightSide) is None
    shell.close_tab(0)
    assert shell.tabs.widget(0) is shell.home


def test_open_game_in_tab_and_reopen_switches_to_it(shell, qapp):
    tab = shell.open_game("good")
    assert tab is not None and shell.tabs.count() == 2
    assert shell.tabs.currentWidget() is tab
    assert shell.tabs.tabText(1) == "Хорошая"
    assert card(shell, "good").play.text() == "Открыта"
    shell.tabs.setCurrentIndex(0)
    assert shell.open_game("good") is tab and shell.tabs.count() == 2
    assert shell.tabs.currentWidget() is tab
    assert tab.ctx.data_dir == os.path.join(shell.root, "good")


def test_broken_game_does_not_open(shell):
    assert shell.open_game("broken_import") is None
    assert shell.open_game("nope") is None
    assert shell.tabs.count() == 1


def test_open_failure_is_shown_and_shell_survives(shell, qapp):
    assert shell.open_game("boom") is None
    assert shell.tabs.count() == 1
    c = card(shell, "boom")
    assert "стол не накрылся" in c.error.text() and not c.error.isHidden()
    assert any("стол не накрылся" in p for p in shell.problems)
    assert shell.open_game("good") is not None


def test_hidden_tab_pauses_timers_and_resumes(shell, qapp):
    tab = shell.open_game("good")
    game = tab.game
    assert wait_until(qapp, lambda: game.ticks > 3)
    shell.tabs.setCurrentIndex(0)                     # вкладку скрыли
    assert tab.paused and not game.timer.isActive()
    frozen = game.ticks
    game.timer.start()                                # игра сама запустила таймер, пока скрыта
    for _ in range(20):
        qapp.processEvents()
        time.sleep(0.003)
    assert game.ticks == frozen and not game.timer.isActive()
    shell.tabs.setCurrentWidget(tab)                  # показали снова
    assert not tab.paused and game.timer.isActive()
    assert wait_until(qapp, lambda: game.ticks > frozen)


def test_switching_between_games_pauses_the_other(shell):
    from fixture_games import hooks
    hooks.CALLS.clear()
    a = shell.open_game("hooks")
    shell.open_game("good")
    assert a.paused and hooks.CALLS == ["pause"]
    shell.tabs.setCurrentWidget(a)
    assert hooks.CALLS == ["pause", "resume"] and not a.paused


def test_minimized_window_pauses_current_game(shell, qapp):
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QWindowStateChangeEvent
    tab = shell.open_game("good")
    shell.setWindowState(Qt.WindowState.WindowMinimized)
    shell.changeEvent(QWindowStateChangeEvent(Qt.WindowState.WindowNoState))
    assert tab.paused and not tab.game.timer.isActive()
    shell.setWindowState(Qt.WindowState.WindowNoState)
    shell.changeEvent(QWindowStateChangeEvent(Qt.WindowState.WindowMinimized))
    assert not tab.paused and tab.game.timer.isActive()
    assert QEvent.Type.WindowStateChange


def test_close_tab_shuts_game_down_and_frees_widgets(shell, qapp):
    from PySide6.QtWidgets import QApplication
    from shiboken6 import isValid
    flush(qapp)
    base = len(QApplication.allWidgets())
    tab = shell.open_game("good")
    game, ctx = tab.game, tab.ctx
    flush(qapp)
    assert len(QApplication.allWidgets()) > base
    shell.close_tab(shell.tabs.indexOf(tab))
    assert game.shutdowns == 1 and not game.timer.isActive()
    flush(qapp)
    assert not isValid(game) and not isValid(ctx)
    assert len(QApplication.allWidgets()) == base
    assert shell.tabs.count() == 1 and shell.current is None
    assert card(shell, "good").play.text() == "Играть"


def test_slow_shutdown_is_reported(shell, monkeypatch):
    from shell import gametab
    monkeypatch.setattr(gametab, "SHUTDOWN_LIMIT", -1.0)
    tab = shell.open_game("good")
    shell.close_game(tab)
    assert any("дольше" in p for p in shell.problems)


def test_theme_and_language_reach_open_games_and_persist(shell, qapp):
    tab = shell.open_game("good")
    shell.set_theme("light")
    shell.set_lang("en")
    assert tab.ctx.theme == "light" and tab.ctx.lang == "en"
    assert tab.game.seen == ["theme", "lang"]
    assert shell.tabs.tabText(0) == "Games" and shell.tabs.tabText(1) == "Good"
    assert shell.windowTitle().startswith("AI Game Room")
    assert card(shell, "good").play.text() == "Open"
    assert "light" in shell.styleSheet() or shell.styleSheet()
    host = json.load(open(os.path.join(shell.root, "host.json"), encoding="utf-8"))
    assert host["theme"] == "light" and host["lang"] == "en"


def test_theme_changed_inside_a_game_reaches_shell_and_other_games(shell):
    a = shell.open_game("good")
    b = shell.open_game("hooks")
    a.ctx.set_theme("light")              # игра сменила тему в своих настройках
    a.ctx.set_lang("en")
    assert shell.theme == "light" and b.ctx.theme == "light"
    assert shell.lang == "en" and b.ctx.lang == "en"
    assert shell.home.theme_buttons["light"].isChecked()
    assert shell.tabs.tabText(0) == "Games"


def test_volume_is_shared(shell):
    tab = shell.open_game("good")
    shell.home.volume.setValue(25)
    assert shell.volume == 25 and tab.ctx.sound.volume == 25


def test_language_note_for_russian_only_game(shell):
    shell.set_lang("en")
    assert "Russian only" in card(shell, "hooks").note.text()
    assert "Russian only" not in card(shell, "good").note.text()


def test_search_filters_cards(shell, qapp):
    shell.home.search.setText("взрыв")
    shown = shell.home.visible_cards()
    assert [c.entry.id for c in shown] == ["boom"]
    shell.home.search.setText("SAMPLE WITHOUT")
    assert [c.entry.id for c in shell.home.visible_cards()] == ["good"]
    shell.home.search.setText("zzzz")
    assert shell.home.visible_cards() == [] and not shell.home.empty.isHidden()
    shell.home.search.setText("")
    assert len(shell.home.visible_cards()) == len(shell.entries)


def test_cards_reflow_by_width(shell, qapp):
    shell.resize(1500, 820)
    flush(qapp)
    wide = shell.home.columns
    shell.resize(900, 820)
    flush(qapp)
    assert wide > shell.home.columns >= 1


def test_close_window_shuts_all_games_and_saves_place(make_shell, qapp, tmp_path):
    from tests.conftest import FIXTURE_GAMES as games
    w = make_shell(games, tmp_path / "h")
    tab = w.open_game("good")
    game = tab.game
    w.resize(1000, 700)
    w.move(40, 30)
    qapp.processEvents()
    w.close()
    assert game.shutdowns == 1 and w.tabs.count() == 1
    saved = json.load(open(tmp_path / "h" / "window.json", encoding="utf-8"))
    assert saved["width"] == 1000 and saved["height"] == 700
    from aikit.window_state import restore, work_areas
    from shell.window import WINDOW_OPTS
    want = restore(saved, work_areas(), WINDOW_OPTS)   # экран offscreen мал - правило то же, что в окне
    again = make_shell(games, tmp_path / "h", place=False)
    assert (again.width(), again.height()) == (want["width"], want["height"])
    assert want["height"] == 700


def test_window_state_survives_garbage_file(make_shell, tmp_path):
    root = tmp_path / "g"
    root.mkdir()
    (root / "window.json").write_text("{мусор", encoding="utf-8")
    (root / "host.json").write_text('{"theme": "neon", "lang": "de", "volume": 999}', encoding="utf-8")
    w = make_shell(FIXTURE_GAMES, root)
    assert w.width() >= 900 and w.height() >= 640
    assert (w.theme, w.lang, w.volume) == ("dark", "ru", 70)


def test_strings_have_both_languages():
    from shell.strings import TABLES, translator
    assert set(TABLES["ru"]) == set(TABLES["en"])
    assert translator("en").missing() == {}


def test_no_games_folder_shows_empty_home(make_shell, tmp_path):
    w = make_shell(str(tmp_path / "empty_games"))
    assert w.entries == [] and not w.home.empty.isHidden()
    assert w.home.empty.text() == "В папке games/ пока нет игр"


def test_shared_statistics_on_cards(make_shell, tmp_path, qapp):
    from aikit.stats import Stats
    root = tmp_path / "s"
    st = Stats(str(root / "good" / "stats.json"))
    for result in ("win", "win", "loss", "win"):
        st.record("2p/strong", result)
    Stats(str(root / "hooks" / "stats.json")).record("x", "draw")
    w = make_shell(FIXTURE_GAMES, root)
    assert card(w, "good").played.text() == "партий 4 · побед 3 · лучшая серия 2"
    assert card(w, "boom").played.text() == "ещё не играли"
    assert card(w, "broken_import").played.isHidden()
    assert w.home.count.text() == "Игр: 3 · Партий во всех играх: 5"
    tab = w.open_game("good")                 # партия сыграна в игре - видно, вернувшись в список
    tab.ctx.stats.record("2p/strong", "win")
    w.tabs.setCurrentIndex(0)
    assert card(w, "good").played.text() == "партий 5 · побед 4 · лучшая серия 2"
    w.set_lang("en")
    assert card(w, "good").played.text() == "5 games · 4 wins · best streak 2"


def test_statistics_survive_broken_file(make_shell, tmp_path):
    root = tmp_path / "b"
    (root / "good").mkdir(parents=True)
    (root / "good" / "stats.json").write_text("{битый", encoding="utf-8")
    w = make_shell(FIXTURE_GAMES, root)
    assert card(w, "good").played.text() == "ещё не играли"
