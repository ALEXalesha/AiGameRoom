"""Окно оболочки: вкладка «Игры» и по вкладке на каждую открытую игру.

Общее для игр - aikit.Context у каждой своей папкой данных (%APPDATA%\\AiGameRoom\\<id>),
а тема, язык и громкость общие (host.json): сменили в оболочке или в любой игре через
ctx.set_theme/set_lang - оболочка разносит это по всем открытым играм.
"""
import gc
import os
import sys

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QMainWindow, QTabBar, QTabWidget

from aikit import data_root, settings
from aikit.host import Context, host_schema
from aikit.window_state import WindowMemory
from shell import registry, style
from shell.gametab import GameTab
from shell.home import HomePage
from shell.strings import translator
from shell.version import VERSION

APP_NAME = "AiGameRoom"
WINDOW_OPTS = {"width": 1240, "height": 820, "minWidth": 900, "minHeight": 640}


class ShellWindow(QMainWindow):
    def __init__(self, games_dir=registry.GAMES_DIR, root=None):
        super().__init__()
        self.root = root or data_root(APP_NAME)
        self.host = settings.Settings(host_schema(), os.path.join(self.root, "host.json"))
        # Тема и язык, которые сейчас на экране. Отдельно от host: игра через ctx пишет в
        # host раньше, чем оболочка узнаёт о смене по ctx.changed.
        self._theme = self.host["theme"]
        self._lang = self.host["lang"]
        self.t = translator(self._lang)
        self.problems = []              # ошибки игр: оболочка их пережила, но они были
        self.entries = registry.discover(games_dir)
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(False)
        self.tabs.tabBar().setDrawBase(False)       # без светлой линии базы Fusion под вкладками
        self.setCentralWidget(self.tabs)
        self.home = HomePage(self)
        self.tabs.addTab(self.home, "")
        for side in (QTabBar.ButtonPosition.RightSide, QTabBar.ButtonPosition.LeftSide):
            self.tabs.tabBar().setTabButton(0, side, None)
        self.current = None             # GameTab, что сейчас на экране
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.apply_theme()
        self.retranslate()
        self.setMinimumSize(WINDOW_OPTS["minWidth"], WINDOW_OPTS["minHeight"])
        self.memory = WindowMemory(self, os.path.join(self.root, "window.json"), WINDOW_OPTS)

    # --- общие настройки ---

    @property
    def theme(self):
        return self._theme

    @property
    def lang(self):
        return self._lang

    @property
    def volume(self):
        return self.host["volume"]

    def game_tabs(self):
        return [self.tabs.widget(i) for i in range(1, self.tabs.count())]

    def find_tab(self, game_id):
        return next((g for g in self.game_tabs() if g.entry.id == game_id), None)

    def is_open(self, game_id):
        return self.find_tab(game_id) is not None

    def report(self, text):
        self.problems.append(text)
        print("AiGameRoom:", text, file=sys.stderr)

    def set_theme(self, name):
        if name == self._theme:
            return
        try:
            self.host.set("theme", name)
        except ValueError:
            return
        self._theme = name
        self.apply_theme()
        for g in self.game_tabs():
            g.ctx.set_theme(name)
        self.home.sync()

    def set_lang(self, lang):
        if lang == self._lang:
            return
        try:
            self.host.set("lang", lang)
        except ValueError:
            return
        self._lang = lang
        self.t = translator(lang)
        for g in self.game_tabs():
            g.ctx.set_lang(lang)
        self.retranslate()

    def set_volume(self, volume):
        if volume == self.volume:
            return
        try:
            self.host.set("volume", volume)
        except ValueError:
            return
        for g in self.game_tabs():
            g.ctx.set_volume(volume)

    def on_game_ctx_changed(self, ctx, what):
        """Игра сменила тему или язык у себя в настройках - то же у всех."""
        if what == "theme":
            self.set_theme(ctx.theme)
        elif what == "lang":
            self.set_lang(ctx.lang)

    def apply_theme(self):
        self.setStyleSheet(style.qss(self.theme))

    def retranslate(self):
        self.setWindowTitle(f"{self.t('app')} {VERSION}")
        self.tabs.setTabText(0, self.t("home"))
        for i in range(1, self.tabs.count()):
            g = self.tabs.widget(i)
            self.tabs.setTabText(i, g.entry.title(self.lang))
        self.home.retranslate()

    # --- игры ---

    def entry(self, game_id):
        return next((e for e in self.entries if e.id == game_id and e.ok), None)

    def open_game(self, game_id):
        """Открыть игру во вкладке (уже открыта - перейти к ней). Вернуть GameTab или None."""
        tab = self.find_tab(game_id)
        if tab is not None:
            self.tabs.setCurrentWidget(tab)
            return tab
        entry = self.entry(game_id)
        if entry is None:
            return None
        ctx = Context(os.path.join(self.root, game_id), self.theme, self.lang, self.volume, self.host)
        try:
            tab = GameTab(entry, ctx, self.report)
        except Exception as e:  # noqa: BLE001 - игра не открылась, оболочка живёт
            entry.open_error = f"{type(e).__name__}: {e}"
            self.report(f"{game_id}: не открылась: {entry.open_error}")
            ctx.deleteLater()
            self.home.retranslate()
            return None
        entry.open_error = None
        ctx.changed.connect(lambda what, c=ctx: self.on_game_ctx_changed(c, what))
        index = self.tabs.addTab(tab, entry.title(self.lang))
        self.tabs.setCurrentIndex(index)
        self.home.retranslate()
        return tab

    def on_tab_changed(self, index):
        widget = self.tabs.widget(index)
        new = widget if isinstance(widget, GameTab) else None
        if self.current is not None and self.current is not new:
            self.current.pause()
        self.current = new
        if new is not None:
            new.ctx.sound.set_volume(self.volume)
            if not self.isMinimized():
                new.resume()
        else:
            self.home.retranslate()           # статистика могла измениться, пока шла игра

    def close_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, GameTab):
            self.close_game(widget)

    def close_game(self, tab):
        """Остановить игру, убрать вкладку, удалить виджет и ctx. Вернуть секунды shutdown."""
        seconds = tab.shutdown()
        if self.current is tab:
            self.current = None
        index = self.tabs.indexOf(tab)
        if index >= 0:
            self.tabs.removeTab(index)
        tab.ctx.changed.disconnect()
        tab.setParent(None)
        tab.ctx.deleteLater()
        tab.deleteLater()
        self.home.retranslate()
        gc.collect()
        return seconds

    # --- окно ---

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == QEvent.Type.WindowStateChange and self.current is not None:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                self.current.pause()
            else:
                self.current.resume()

    def moveEvent(self, event):
        super().moveEvent(event)
        if hasattr(self, "memory"):
            self.memory.track()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "memory"):
            self.memory.track()

    def closeEvent(self, event):
        for g in self.game_tabs():
            self.close_game(g)
        self.memory.save()
        super().closeEvent(event)
