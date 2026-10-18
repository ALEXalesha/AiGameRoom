"""Виджет игры: стопка экранов, загрузка моделей. Своего главного окна у игры нет
(контракт PythonAiGames): виджет встаёт во вкладку оболочки AiGameRoom или в окно отдельного
запуска (aikit.make_window, main.py).

- тема, язык и громкость - из ctx и меняются на лету по ctx.changed; сменённые в настройках
  игры уходят в ctx;
- файлы - только в ctx.data_dir: settings.json и stats.json (свой формат, game/ui/store.py),
  звуки в game-sounds;
- pause(): вкладку скрыли - матч встаёт на паузу (карточка «Пауза»), таймер останавливается;
  resume() - таймер снова идёт, матч ждёт «Продолжить», как после ухода окна в фон;
- shutdown(): остановить таймер матча. Потоков у игры нет.
"""
import os

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from games.snake.ai.models import ModelMissing, Models
from games.snake.design.journal import Journal
from games.snake.design.runtime import from_models
from games.snake.ui import store as st
from games.snake.ui import theme
from games.snake.ui.i18n import translator
from games.snake.ui.look import scale_for
from games.snake.ui.screens import MatchScreen, MenuScreen, SettingsScreen, StatsScreen
from games.snake.ui.sound import Sounds

WIDTH, HEIGHT = 1040, 720
MIN_WIDTH, MIN_HEIGHT = 820, 600


def make_icon():
    """Значок окна рисуется кодом: голова змейки на тёмном квадрате."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pix = QPixmap(size, size)
        pix.fill(Qt.GlobalColor.transparent)
        p = QPainter(pix)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = size / 32
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#10141b"))
        p.drawRoundedRect(QRectF(0, 0, size, size), 7 * s, 7 * s)
        p.setBrush(QColor("#34d17c"))
        p.drawRoundedRect(QRectF(4 * s, 13 * s, 16 * s, 8 * s), 4 * s, 4 * s)
        p.setBrush(QColor("#9af7c1"))
        p.drawEllipse(QPointF(21 * s, 17 * s), 6 * s, 6 * s)
        p.setBrush(QColor("#0b0e13"))
        p.drawEllipse(QPointF(23 * s, 15 * s), 1.4 * s, 1.4 * s)
        p.setBrush(QColor("#ff4d6d"))
        p.drawEllipse(QPointF(26 * s, 7 * s), 3 * s, 3 * s)
        p.end()
        icon.addPixmap(pix)
    return icon


class GameWidget(QWidget):
    def __init__(self, ctx, models=None, sounds=None, design=None):
        super().__init__()
        self.ctx = ctx
        self._design_arg = design
        self.store = st.Store(ctx.data_dir)
        self.models = models if models is not None else Models()
        self.sounds = sounds if sounds is not None else Sounds(
            ctx.sound.volume, folder=os.path.join(ctx.data_dir, "game-sounds"))
        self.t = translator(ctx.lang)
        self.closed = False
        self._quit = None
        self._was_running = False
        self._world = None
        self._opponents = {}
        self.setObjectName("gameRoot")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumSize(MIN_WIDTH, MIN_HEIGHT)
        self.style_now = None            # стиль окна (сеть-дизайнер или код); None - основной вид
        self.scale = 1.0                 # масштаб окна: шрифты и размеры растут на больших окнах
        self.theme_name = ctx.theme

        self.stack = QStackedWidget()
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.menu = MenuScreen()
        self.match_screen = MatchScreen(self.store, self.sounds)
        self.stats_screen = StatsScreen(self.store, self.models)
        self.settings_screen = SettingsScreen(self.store, ctx)
        self.screens = (self.menu, self.match_screen, self.stats_screen, self.settings_screen)
        for screen in self.screens:
            self.stack.addWidget(screen)
            screen.set_scale(self.scale)      # постоянные размеры элементов (масштаб 1)

        self.menu.play.connect(self.play)
        self.menu.stats.connect(self.show_stats)
        self.menu.settings.connect(self.show_settings)
        self.menu.quit.connect(self.quit)
        # «Выход» - только в окне отдельного запуска (main.py включает его через allow_quit):
        # во вкладке оболочки игру закрывает крестик вкладки
        self.menu.quit_button.setVisible(False)
        self.match_screen.to_menu.connect(self.show_menu)
        self.match_screen.again.connect(self.play)
        self.stats_screen.back.connect(self.show_menu)
        self.settings_screen.back.connect(self.show_menu)
        self.settings_screen.changed.connect(self._setting_changed)

        # 2.0: окно раскладывает сеть-дизайнер, клетки рисует сеть-художник (game/design);
        # design=False - всё кодом без шума (обучение дизайнера), объект - подмена в тестах
        if design is None:
            self.journal = Journal(ctx.data_dir)
            design = from_models(self.models, self.journal)
        else:
            self.journal = design.journal if design else Journal(ctx.data_dir)
        self.design = design or None
        self.stats_screen.journal = self.journal
        if self.design is not None:
            k = self.design.knobs()
            for screen in self.screens:
                screen.set_knobs(k)
                screen.design = self.design
            for b in (self.match_screen.board, self.menu.logo, self.settings_screen.preview):
                b.set_tiles(self.design.tiles)

        self.match_screen.board.set_palette(self.store.settings["palette"])
        self.apply_theme(ctx.theme)
        self.retranslate()
        ctx.changed.connect(self.on_ctx_changed)
        self.show_menu()

    # --- экраны ------------------------------------------------------------------------

    def show_menu(self):
        self.match_screen.stop()
        self.menu.set_info(self.store.settings)
        self.stack.setCurrentWidget(self.menu)
        self.menu.play_button.setFocus()

    def show_stats(self):
        self.menu.show_message("")
        self.stats_screen.refresh()
        self.stack.setCurrentWidget(self.stats_screen)
        self.stats_screen.setFocus()

    def show_settings(self):
        self.menu.show_message("")
        self.settings_screen.load()
        self.stack.setCurrentWidget(self.settings_screen)
        self.settings_screen.setFocus()

    def play(self):
        level = self.store.settings["opponent"]
        try:
            if self._world is None:
                self._world = self.models.load_world()
            if level not in self._opponents:
                self._opponents[level] = self.models.load_opponent(level)
        except ModelMissing as err:
            self._fail(str(err))
            return
        except Exception as err:  # noqa: BLE001 - любая беда с моделью - текст в окне
            self._fail(self.t("load_failed", err=err))
            return
        self.menu.show_message("")
        if self.design is not None and hasattr(self.design.tiles, "new_match"):
            self.design.tiles.new_match()       # новая партия - новая «рука» художника
        self.stack.setCurrentWidget(self.match_screen)
        self.match_screen.start(self._world, self._opponents[level], level)

    def _fail(self, text):
        self.show_menu()
        self.menu.show_message(text)

    def allow_quit(self, slot):
        """Окно отдельного запуска: показать «Выход» в меню; slot закрывает окно."""
        self._quit = slot
        self.menu.quit_button.setVisible(True)
        self.menu.relayout()

    def quit(self):
        if self._quit is not None:
            self._quit()

    def _setting_changed(self, key):
        if key == "palette":
            self.match_screen.apply_settings()
            self.menu.set_info(self.store.settings)
        elif key == "volume":
            self.sounds.set_volume(self.ctx.sound.volume)
        elif key == "sound_check":
            self.play_sound("eat")

    def play_sound(self, name):
        # громкость общая и в оболочке меняется без сигнала - сверяется перед звуком
        if self.sounds.volume != self.ctx.sound.volume:
            self.sounds.set_volume(self.ctx.sound.volume)
        self.sounds.play(name)

    # --- тема и язык на лету -------------------------------------------------------------

    def on_ctx_changed(self, what):
        if what == "theme":
            self.apply_theme(self.ctx.theme)
        elif what == "lang":
            self.t = translator(self.ctx.lang)
            if self.design is not None:
                # сначала стиль и язык дизайнера, потом тексты: раскладка под новый язык
                # должна считаться уже с новыми текстами (иначе законы видят старые слова и
                # раскладка навсегда уходит в запасной вариант - поймано самопроверкой 17.10)
                self.apply_theme(self.ctx.theme, relayout=False)
            self.retranslate()
        if self.stack.currentWidget() is self.settings_screen:
            self.settings_screen.load()

    def apply_theme(self, name, relayout=True):
        style = self.design.style(name, self.ctx.lang) if self.design is not None else None
        self.style_now = style               # стиль окна сейчас (None - основной вид без шума)
        self.theme_name = name
        self.restyle()
        self.setPalette(theme.palette(name, style))
        for screen in self.screens:
            screen.set_theme(name)
        current = self.stack.currentWidget()
        if current is not None and relayout:
            current.relayout()

    def restyle(self):
        """Таблица стилей по теме, стилю и масштабу окна."""
        self.setStyleSheet(theme.qss(self.theme_name, self.style_now, self.scale))

    def set_scale(self, k):
        """Масштаб окна (game/ui/look.scale_for): на 4K без масштаба Windows меню и панель матча
        были крошечными (проверка 17.10). Сеть-дизайнер видит те же размеры, что и код-учитель."""
        if k == self.scale:
            return
        self.scale = k
        self.restyle()
        for screen in self.screens:
            screen.set_scale(k)
        current = self.stack.currentWidget()
        if current is not None:
            current.relayout()

    def resizeEvent(self, event):
        self.set_scale(scale_for(self.width(), self.height()))
        super().resizeEvent(event)

    def retranslate(self):
        for screen in self.screens:
            screen.retranslate(self.t)

    # --- жизнь во вкладке оболочки и в окне -----------------------------------------------

    def pause(self):
        self.menu.pause()                    # живой фон меню не тикает в скрытой вкладке
        self.match_screen.auto_pause()
        self._was_running = self.match_screen.timer.isActive()
        self.match_screen.stop()

    def resume(self):
        self.menu.resume()
        if self._was_running and not self.closed and self.match_screen.match is not None:
            self.match_screen.clock.restart()
            self.match_screen.timer.start()
        self._was_running = False

    def shutdown(self):
        """Остановить таймер матча; потоков нет. True - всё остановлено. Матч, брошенный после
        сыгранного раунда, - поражение (как в КНБ 1.0.4)."""
        self.closed = True
        self.menu.pause()
        self.match_screen.abandon()
        self.match_screen.stop()
        self.store.save_stats()
        self.journal.save()
        return True

    def changeEvent(self, event):
        # окно ушло в фон посреди матча - пауза, чтобы змейка не разбилась сама
        if event.type() == QEvent.Type.ActivationChange and not self.isActiveWindow() \
                and self.stack.currentWidget() is self.match_screen:
            self.match_screen.auto_pause()
        super().changeEvent(event)
