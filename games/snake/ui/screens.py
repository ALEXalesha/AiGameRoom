"""Экраны виджета игры: меню, матч, статистика, настройки.

Тексты - через переводчик (game/ui/i18n.py): у каждого экрана retranslate(t), язык
меняется на лету. Цвета, которые рисуются не через QSS, - через set_theme(name).
"""
import numpy as np
from PySide6.QtCore import QElapsedTimer, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QProgressBar, QPushButton, QScrollArea, QSizePolicy, QSlider,
                               QVBoxLayout, QWidget)

from games.snake.core import match as M
from games.snake.core.cells import DOWN, LEFT, RIGHT, UP, build
from games.snake.ui import store as st
from games.snake.ui import theme
from games.snake.ui.board import PALETTES, Board
from games.snake.ui.chart import Chart, points_from
from games.snake.ui.i18n import LANG_NAMES, translator

# Клавиши -> направление. Кириллица - это W A S D на русской раскладке (Ц Ф Ы В).
KEY_DIRS = {
    int(Qt.Key.Key_Up): UP, int(Qt.Key.Key_W): UP, 0x0426: UP,
    int(Qt.Key.Key_Down): DOWN, int(Qt.Key.Key_S): DOWN, 0x042B: DOWN,
    int(Qt.Key.Key_Left): LEFT, int(Qt.Key.Key_A): LEFT, 0x0424: LEFT,
    int(Qt.Key.Key_Right): RIGHT, int(Qt.Key.Key_D): RIGHT, 0x0412: RIGHT,
}
# Коды клавиш Windows - не зависят от раскладки (на всякий случай для других раскладок).
VK_DIRS = {0x57: UP, 0x53: DOWN, 0x41: LEFT, 0x44: RIGHT}

TARGET = 3
# Надписи на поле в конце раунда (рисует Board.caption_layout), по-русски - для законов о
# размере надписи; в игре они берутся из переводчика.
ROUND_TEXT = {"win": "Раунд ваш!", "lose": "Раунд за сетью", "draw": "Ничья"}
DRAW_SUBTEXT = "обе змейки врезались - очко никому"


def label(text="", name=None, wrap=False):
    lb = QLabel(text)
    if name:
        lb.setObjectName(name)
    lb.setWordWrap(wrap)
    return lb


class HintLabel(QLabel):
    """Подсказка с переносом, которая держит место под lines строк, даже если текст короче.

    Высота строки настроек тогда не прыгает, когда подсказка переносится на строку больше или
    меньше: сеть-дизайнер не угадывает порог переноса, а учит ровную высоту (17.10 строки
    настроек с подсказкой были 2/3 всех провалов законов). Предела по высоте нет - длиннее
    lines строк подсказка растёт как обычная метка."""

    def __init__(self, lines=3):
        super().__init__("")
        self.setObjectName("muted")
        self.setWordWrap(True)
        self.lines = lines

    def _reserve(self):
        return self.fontMetrics().lineSpacing() * self.lines

    def heightForWidth(self, w):
        return max(super().heightForWidth(w), self._reserve())

    def minimumSizeHint(self):
        size = super().minimumSizeHint()
        size.setHeight(max(size.height(), self._reserve()))
        return size

    def sizeHint(self):
        size = super().sizeHint()
        size.setHeight(max(size.height(), self._reserve()))
        return size


def separator():
    line = QFrame()
    line.setObjectName("separator")
    return line


def button(text="", primary=False, focus=True):
    b = QPushButton(text)
    if primary:
        b.setObjectName("primary")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if not focus:
        b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return b


def card():
    f = QFrame()
    f.setObjectName("card")
    return f


class Texts:
    """Подписи экрана: label/кнопка -> ключ перевода. apply(t) расставляет текст.
    upper - заголовки разделов заглавными буквами."""

    def __init__(self):
        self.items = []

    def add(self, widget, key, upper=False):
        self.items.append((widget, key, upper))
        return widget

    def apply(self, t):
        for widget, key, upper in self.items:
            text = t(key)
            widget.setText(text.upper() if upper else text)


def mini_board():
    """Маленькое поле-картинка: две змейки тянутся к еде (для меню и настроек)."""
    field = build(4, 14, [[(3, 1), (3, 2), (3, 3), (2, 3), (2, 4), (2, 5)],
                          [(0, 12), (1, 12), (2, 12), (2, 11), (2, 10), (2, 9)]], food=[(2, 7)])
    b = Board(framed=False)
    b.setMinimumSize(0, 0)
    b.setFixedSize(14 * 20, 4 * 20)
    b.set_state(field)
    return b


def pct(v, digits=1):
    return f"{v * 100:.{digits}f}%"


class Screen(QWidget):
    """Экран. Для сети-дизайнера (game/design) экран сообщает список своих элементов -
    elements(), раскладки, которые в режиме ИИ выключаются, - design_layouts(), и умеет
    менять поля и промежутки по ручкам кода - set_knobs()."""

    NAME = ""                 # имя экрана для сети-дизайнера (game/design/designer_net.SCREENS)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("screen")
        self.t = translator("ru")
        self.colors = theme.tokens("dark")
        self.texts = Texts()
        self._tracked = []        # (раскладка, базовые поля, базовый промежуток)
        self._gaps = []           # (раскладка, распорка, базовый размер)
        self.design = None        # game/design/runtime.AiDesign или None - раскладка кода

    def track(self, layout):
        """Запомнить поля и промежуток раскладки как базовые (z = 0) для set_knobs."""
        m = layout.contentsMargins()
        self._tracked.append((layout, (m.left(), m.top(), m.right(), m.bottom()), layout.spacing()))
        return layout

    def gap(self, layout, px):
        """addSpacing, который тоже растягивается ручкой промежутков."""
        layout.addSpacing(px)
        self._gaps.append((layout, layout.itemAt(layout.count() - 1).spacerItem(), px))

    def set_knobs(self, k):
        """Поля - на k.margin, промежутки и распорки - на k.spacing (game/design/knobs.py)."""
        for lay, m, sp in self._tracked:
            lay.setContentsMargins(*(round(v * k.margin) for v in m))
            if sp >= 0:
                lay.setSpacing(round(sp * k.spacing))
        for lay, item, px in self._gaps:
            v = round(px * k.spacing)
            if isinstance(lay, QHBoxLayout):
                item.changeSize(v, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
            else:
                item.changeSize(0, v, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
            lay.invalidate()

    def elements(self):
        """[(имя, виджет, имя родителя или None)] - что раскладывает сеть-дизайнер; родитель
        всегда раньше своих детей."""
        return []

    def design_layouts(self):
        """Раскладки, которые в режиме ИИ выключены: их работу делает сеть-дизайнер."""
        return [self.layout()]

    def flags(self):
        """Что из необязательного видно (меню: «Выход», сообщение) - вход сети-дизайнера."""
        return (0, 0)

    def header(self, title_key, back):
        """Заголовок экрана с кнопкой «В меню» справа."""
        row = QHBoxLayout()
        self.title_label = self.texts.add(label("", "screenTitle"), title_key)
        row.addWidget(self.title_label)
        row.addStretch(1)
        b = self.texts.add(button(), "to_menu")
        b.clicked.connect(back)
        row.addWidget(b)
        self.back_button = b
        return row

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.design is not None:
            self.design.layout(self)

    def showEvent(self, event):
        super().showEvent(event)
        if self.design is not None:
            self.design.layout(self)

    def relayout(self):
        """Видимость или тексты поменялись - раскладка заново (у кода - сама Qt)."""
        if self.design is not None and self.isVisible():
            self.design.layout(self)

    def retranslate(self, t):
        self.t = t
        self.texts.apply(t)
        self.relayout()

    def set_theme(self, name):
        self.colors = theme.tokens(name)


# --- меню -----------------------------------------------------------------------------


class MenuScreen(Screen):
    NAME = "menu"
    play = Signal()
    stats = Signal()
    settings = Signal()
    quit = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._settings = None
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 24)
        self.track(outer)
        outer.addStretch(3)

        self.logo = mini_board()
        outer.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.gap(outer, 12)
        title = self.texts.add(label("", "title"), "title")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(title)
        self.title_label = title
        sub = self.texts.add(label("", "subtitle"), "subtitle")
        sub.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(sub)
        self.subtitle = sub
        self.gap(outer, 26)

        column = QVBoxLayout()
        column.setSpacing(10)
        self.track(column)
        self.play_button = self.texts.add(button(primary=True), "play")
        self.stats_button = self.texts.add(button(), "stats")
        self.settings_button = self.texts.add(button(), "settings")
        self.quit_button = self.texts.add(button(), "quit")
        for b, sig in ((self.play_button, self.play), (self.stats_button, self.stats),
                       (self.settings_button, self.settings), (self.quit_button, self.quit)):
            b.setFixedWidth(300)
            b.clicked.connect(sig)
            column.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addLayout(column)
        self.gap(outer, 16)

        self.message = label("", "warning", wrap=True)
        self.message.setFixedWidth(560)      # с переносом строк и выравниванием по центру
                                             # иначе Qt считает высоту на одну строку
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message.hide()
        outer.addWidget(self.message, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(4)

        self.info = label("", "muted")
        self.info.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(self.info)

    def show_message(self, text):
        self.message.setText(text)
        self.message.setVisible(bool(text))
        self.relayout()

    def elements(self):
        return [("logo", self.logo, None), ("title", self.title_label, None), ("subtitle", self.subtitle, None),
                ("play", self.play_button, None), ("stats", self.stats_button, None),
                ("settings", self.settings_button, None), ("quit", self.quit_button, None),
                ("message", self.message, None), ("info", self.info, None)]

    def flags(self):
        return (int(not self.quit_button.isHidden()), int(not self.message.isHidden()))

    def set_info(self, settings):
        self._settings = dict(settings)
        self.info.setText(self.t("menu_info", level=self.t("level_" + settings["opponent"]),
                                 ms=settings["speed_ms"], target=TARGET))
        self.logo.set_palette(settings["palette"])

    def retranslate(self, t):
        super().retranslate(t)
        if self._settings is not None:
            self.set_info(self._settings)


# --- матч -----------------------------------------------------------------------------


class Overlay(QWidget):
    """Затемнение поверх поля с карточкой: пауза, конец матча или сбой сети."""

    def __init__(self, parent):
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("overlayCard")
        self.card.setFixedWidth(340)
        box = QVBoxLayout(self.card)
        box.setContentsMargins(26, 22, 26, 22)
        box.setSpacing(10)
        self.title = label("", "overlayTitle")
        self.title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.text = label("", "muted", wrap=True)
        self.text.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        box.addWidget(self.title)
        box.addWidget(self.text)
        box.addSpacing(8)
        self.buttons = box
        outer.addWidget(self.card, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

    def paintEvent(self, event):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(6, 8, 12, 165))
        p.end()


class MatchScreen(Screen):
    NAME = "match"
    to_menu = Signal()
    again = Signal()

    def __init__(self, store, sounds, parent=None):
        super().__init__(parent)
        self.store = store
        self.sounds = sounds
        self.match = None
        self.level = "medium"
        self._shown = -1
        self._overlay_kind = None        # что на карточке: ("pause",) / ("over", ev) / ("fail", текст)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        row = QHBoxLayout(self)
        row.setContentsMargins(14, 14, 14, 14)
        row.setSpacing(14)
        self.track(row)
        self.board = Board()
        self.board.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        row.addWidget(self.board, 1)
        row.addWidget(self._build_panel())

        self.overlay = Overlay(self.board)
        self.board.overlay = self.overlay
        self.resume_button = self.texts.add(button(primary=True), "continue")
        self.again_button = self.texts.add(button(primary=True), "again")
        self.menu_button = self.texts.add(button(), "to_menu")
        for b in (self.resume_button, self.again_button, self.menu_button):
            self.overlay.buttons.addWidget(b)
        self.resume_button.clicked.connect(self.resume)
        self.again_button.clicked.connect(self.again)
        self.menu_button.clicked.connect(self.leave)
        self.overlay.hide()

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.TimerType.PreciseTimer)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self._tick)
        self.clock = QElapsedTimer()

    def _block(self, box):
        """Блок панели: свой виджет со своей раскладкой - сеть-дизайнер ставит блоки целиком."""
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.track(lay)
        box.addWidget(w)
        return w, lay

    def _build_panel(self):
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedWidth(272)
        box = QVBoxLayout(panel)
        box.setContentsMargins(20, 14, 20, 14)
        box.setSpacing(8)
        self.track(box)
        self.panel = panel
        add = self.texts.add

        self.score_block, lay = self._block(box)
        lay.addWidget(add(label("", "section"), "score", upper=True))
        self.score = label("", "big")
        self.score.setTextFormat(Qt.TextFormat.RichText)
        self.score.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        lay.addWidget(self.score)
        names = QHBoxLayout()
        self.name0 = add(label("", "value"), "you")
        self.name1 = add(label("", "value"), "net")
        names.addWidget(self.name0)
        names.addStretch(1)
        names.addWidget(self.name1)
        lay.addLayout(names)
        self.round_info = label("", "muted")
        lay.addWidget(self.round_info)
        self.gap(lay, 6)
        lay.addWidget(separator())

        self.lengths_block, lay = self._block(box)
        lay.addWidget(add(label("", "section"), "lengths", upper=True))
        grid = QGridLayout()
        self.len0 = label("3", "value")
        self.len1 = label("3", "value")
        grid.addWidget(add(label(), "you"), 0, 0)
        grid.addWidget(self.len0, 0, 1, Qt.AlignmentFlag.AlignRight)
        grid.addWidget(add(label(), "net"), 1, 0)
        grid.addWidget(self.len1, 1, 1, Qt.AlignmentFlag.AlignRight)
        lay.addLayout(grid)
        self.gap(lay, 6)
        lay.addWidget(separator())

        self.conf_block, lay = self._block(box)
        lay.addWidget(add(label("", "section"), "confidence", upper=True))
        conf_row = QHBoxLayout()
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 1000)
        self.conf_bar.setTextVisible(False)
        self.conf_value = label("-", "value")
        self.conf_value.setMinimumWidth(56)
        self.conf_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        conf_row.addWidget(self.conf_bar, 1)
        conf_row.addWidget(self.conf_value)
        lay.addLayout(conf_row)
        lay.addWidget(add(label("", "muted", wrap=True), "confidence_hint"))
        self.gap(lay, 6)
        lay.addWidget(separator())

        self.opponent_block, lay = self._block(box)
        lay.addWidget(add(label("", "section"), "opponent", upper=True))
        self.opponent_info = label("", "value")
        lay.addWidget(self.opponent_info)
        box.addStretch(1)

        self.keys_label = add(label("", "muted"), "keys")
        box.addWidget(self.keys_label)
        self.pause_button = add(button(focus=False), "pause")
        self.pause_button.clicked.connect(self.pause)
        box.addWidget(self.pause_button)
        return panel

    def elements(self):
        return [("board", self.board, None), ("panel", self.panel, None),
                ("score_block", self.score_block, "panel"), ("lengths_block", self.lengths_block, "panel"),
                ("conf_block", self.conf_block, "panel"), ("opponent_block", self.opponent_block, "panel"),
                ("keys", self.keys_label, "panel"), ("pause", self.pause_button, "panel")]

    def design_layouts(self):
        return [self.layout(), self.panel.layout()]

    def retranslate(self, t):
        super().retranslate(t)
        if self.match is not None:
            self._refresh()
            if self.overlay.isVisible() and self._overlay_kind is not None:
                self._show_kind(self._overlay_kind)

    def set_theme(self, name):
        super().set_theme(name)
        if self.match is not None:
            self._refresh()

    # --- управление ------------------------------------------------------------------

    def start(self, world, opponent, level):
        s = self.store.settings
        self.level = level
        self.match = M.Match(world, opponent, np.random.default_rng(), target=TARGET,
                             speed_ms=s["speed_ms"])
        self.board.set_palette(s["palette"])
        self.overlay.hide()
        self._overlay_kind = None
        self._shown = -1
        self._process()
        self._refresh()
        self.clock.start()
        self.timer.start()
        self.setFocus()

    def stop(self):
        self.timer.stop()

    def leave(self):
        self.stop()
        self.match = None
        self.overlay.hide()
        self.to_menu.emit()

    def pause(self):
        m = self.match
        if m is None or m.paused or m.phase == M.MATCH_OVER:
            return
        m.paused = True
        self._show_kind(("pause",))

    def resume(self):
        if self.match is None:
            return
        self.match.paused = False
        self.overlay.hide()
        self._overlay_kind = None
        self.clock.restart()
        self.setFocus()

    def auto_pause(self):
        """Окно ушло в фон или вкладку скрыли - змейка не должна разбиться сама."""
        if self.match is not None and self.match.phase in (M.COUNTDOWN, M.PLAYING):
            self.pause()

    def _show_kind(self, kind):
        t = self.t
        self._overlay_kind = kind
        if kind[0] == "pause":
            self._show_overlay(t("pause"), t("pause_hint"), (self.resume_button, self.menu_button))
        elif kind[0] == "over":
            a, b = self.match.score
            self._show_overlay(t("match_win") if kind[1] == "win" else t("match_loss"),
                               t("match_result", a=a, b=b, level=t("level_" + self.level).lower()),
                               (self.again_button, self.menu_button))
        else:
            self._show_overlay(t("net_failure"), kind[1], (self.menu_button,))

    def _show_overlay(self, title, text, buttons):
        self.overlay.title.setText(title)
        self.overlay.text.setText(text)
        for b in (self.resume_button, self.again_button, self.menu_button):
            b.setVisible(b in buttons)
        self.overlay.setGeometry(self.board.rect())
        self.overlay.show()
        self.overlay.raise_()
        buttons[0].setFocus()

    # --- время -----------------------------------------------------------------------

    def _tick(self):
        dt = self.clock.restart()
        self.advance(min(dt, 250))

    def advance(self, dt_ms):
        """Шаг времени: из таймера или из тестов."""
        if self.match is None:
            return
        try:
            self.match.update(dt_ms)
        except Exception as err:  # noqa: BLE001 - сбой сети не роняет окно
            self.stop()
            self._show_kind(("fail", str(err) or type(err).__name__))
            return
        self._process()
        if self.match.version != self._shown:
            self._refresh()

    def _process(self):
        m = self.match
        stats = self.store.stats
        for ev in m.take_events():
            self.sounds.on_event(ev)
            if ev.startswith("round_"):
                st.record_round(stats, self.level, m.round_result, m.longest[0], m.round_eaten[0])
                self.store.save_stats()
            elif ev in ("win", "lose"):
                st.record_match(stats, self.level, ev == "win")
                self.store.save_stats()
                self._show_kind(("over", ev))

    # --- вид ---------------------------------------------------------------------------

    def _refresh(self):
        m = self.match
        s = self.store.settings
        t = self.t
        self._shown = m.version
        text = sub = ""
        if m.phase == M.COUNTDOWN:
            text, sub = str(m.count), t("countdown_sub", round=m.round)
        elif m.phase == M.ROUND_OVER:
            text = t("round_" + m.round_result)
            sub = t("draw_sub") if m.round_result == "draw" else t("score_sub", a=m.score[0], b=m.score[1])
        self.board.set_state(m.field, m.food_probs, s["show_food_map"], m.crashed, text, sub)

        pal = PALETTES[self.board.palette_index]
        c0, c1 = pal["label"]
        self.score.setText(f"<span style='color:{c0}'>{m.score[0]}</span>"
                           f"<span style='color:{self.colors['score_sep']}'> : </span>"
                           f"<span style='color:{c1}'>{m.score[1]}</span>")
        self.name0.setStyleSheet(f"color: {c0};")
        self.name1.setStyleSheet(f"color: {c1};")
        self.round_info.setText(t("round_info", round=m.round, target=m.target))
        l0, l1 = m.lengths()
        self.len0.setText(str(l0))
        self.len1.setText(str(l1))
        conf = m.confidence
        if conf is None:
            self.conf_bar.setValue(0)
            self.conf_value.setText("-")
            level = "good"
        else:
            self.conf_bar.setValue(int(round(conf * 1000)))
            self.conf_value.setText(pct(conf))
            level = "good" if conf >= 0.9 else "mid" if conf >= 0.6 else "bad"
        if self.conf_bar.property("level") != level:
            self.conf_bar.setProperty("level", level)
            self.conf_bar.style().unpolish(self.conf_bar)
            self.conf_bar.style().polish(self.conf_bar)
        self.opponent_info.setText(t("opponent_info", level=t("level_" + self.level), ms=m.speed_ms))

    def apply_settings(self):
        self.board.set_palette(self.store.settings["palette"])
        if self.match is not None:
            self._refresh()

    def keyPressEvent(self, event):
        key = int(event.key())
        if key == int(Qt.Key.Key_Escape):
            if self.match is None:
                return
            if self.match.phase == M.MATCH_OVER or self.overlay.isVisible() and \
                    not self.match.paused:
                self.leave()
            elif self.match.paused:
                self.resume()
            else:
                self.pause()
            return
        d = KEY_DIRS.get(key)
        if d is None:
            d = VK_DIRS.get(int(event.nativeVirtualKey()))
        if d is not None and self.match is not None:
            self.match.press(d)
            event.accept()
            return
        super().keyPressEvent(event)


# --- статистика -----------------------------------------------------------------------


ACCURACY_ROWS = (("field_symmetric", 0.995, True), ("field", 0.995, True), ("events", 0.999, True),
                 ("food_on_occupied", 0.01, False))


class StatsScreen(Screen):
    NAME = "stats"
    back = Signal()

    def __init__(self, store, models, parent=None):
        super().__init__(parent)
        self.store = store
        self.models = models
        add = self.texts.add
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 16)
        self.track(outer)
        outer.addLayout(self.header("stats", self.back.emit))
        self.gap(outer, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("scrollBody")
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)
        self.scroll = scroll
        box = QVBoxLayout(body)
        box.setContentsMargins(0, 0, 8, 8)
        box.setSpacing(14)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        self.values = {}
        for key in ("matches", "rounds", "longest", "food"):
            c = card()
            v = QVBoxLayout(c)
            v.setContentsMargins(16, 12, 16, 12)
            self.values[key] = label("0", "cardValue")
            v.addWidget(self.values[key])
            v.addWidget(add(label("", "muted"), "card_" + key))
            cards.addWidget(c, 1)
        box.addLayout(cards)

        levels = card()
        grid = QGridLayout(levels)
        grid.setContentsMargins(18, 14, 18, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        for col, key in enumerate(("head_opponent", "head_matches", "head_rounds", "head_vs_bot")):
            grid.addWidget(add(label("", "section"), key, upper=True), 0, col, Qt.AlignmentFlag.AlignBottom)
        grid.setColumnStretch(3, 1)
        self.level_cells = {}
        for row, lv in enumerate(st.LEVELS, start=1):
            grid.addWidget(add(label("", "value"), "level_" + lv), row, 0)
            for col, key in enumerate(("matches", "rounds", "win_vs_bot"), start=1):
                cell = label("0")
                self.level_cells[lv, key] = cell
                grid.addWidget(cell, row, col)
        box.addWidget(levels)

        world = card()
        wv = QVBoxLayout(world)
        wv.setContentsMargins(18, 14, 18, 14)
        wv.addWidget(add(label("", "section"), "world_accuracy", upper=True))
        self.world_label = label("", wrap=True)
        self.world_label.setTextFormat(Qt.TextFormat.RichText)
        wv.addWidget(self.world_label)
        box.addWidget(world)

        # 2.0: окно и поле делают сети - насколько окно отличается от кодового и сколько раз
        # сработал запасной вариант (журнал game/design/journal.py)
        design = card()
        dv = QVBoxLayout(design)
        dv.setContentsMargins(18, 14, 18, 14)
        dv.addWidget(add(label("", "section"), "design_card", upper=True))
        self.design_label = label("", wrap=True)
        self.design_label.setTextFormat(Qt.TextFormat.RichText)
        dv.addWidget(self.design_label)
        box.addWidget(design)
        self.journal = None            # ставит виджет игры
        self._design = ({}, {}, None)

        charts = QGridLayout()
        charts.setSpacing(12)
        self.chart_world_loss = Chart("", "#ff8a3d", "", log_y=True)
        self.chart_world_field = Chart("", "#34d17c", "", percent=True)
        self.chart_imitation = Chart("", "#4fc3f7", "", percent=True)
        self.chart_rl = Chart("", "#c792ea", "")
        self.chart_designer = Chart("", "#f7c948", "")
        self.chart_painter = Chart("", "#ff7eb6", "", percent=True)
        self.charts = [self.chart_world_loss, self.chart_world_field, self.chart_imitation,
                       self.chart_rl, self.chart_designer, self.chart_painter]
        self.chart_keys = (("chart_world_loss", "x_step"), ("chart_world_field", "x_step"),
                           ("chart_imitation", "x_step"), ("chart_rl", "x_episode"),
                           ("chart_designer", "x_step"), ("chart_painter", "x_step"))
        for i, c in enumerate(self.charts):
            charts.addWidget(c, i // 2, i % 2)
        box.addLayout(charts)
        self.no_charts = add(label("", "muted", wrap=True), "no_charts")
        box.addWidget(self.no_charts)
        box.addStretch(1)
        self._final = {}

    def retranslate(self, t):
        super().retranslate(t)
        for c, (title, x) in zip(self.charts, self.chart_keys):
            c.set_text(t(title), t(x))
        self.world_label.setText(self._accuracy(self._final))
        self.design_label.setText(self._design_text(*self._design))

    def set_theme(self, name):
        super().set_theme(name)
        for c in self.charts:
            c.set_theme(name)
        self.world_label.setText(self._accuracy(self._final))
        self.design_label.setText(self._design_text(*self._design))

    def refresh(self):
        s = self.store.stats
        for key, v in self.values.items():
            v.setText(str(s[key]))
        player = self.models.load_passport("player") or {}
        levels = player.get("levels") if isinstance(player.get("levels"), dict) else {}
        for lv in st.LEVELS:
            n = s["levels"][lv]
            self.level_cells[lv, "matches"].setText(f"{n['match_wins']} / {n['match_losses']}")
            self.level_cells[lv, "rounds"].setText(f"{n['wins']} / {n['losses']} / {n['draws']}")
            info = levels.get(lv) if isinstance(levels.get(lv), dict) else {}
            # паспорт обучения (game/train/player_train.py): levels.<уровень>.vs_bot.win - доля от 0 до 1
            vs_bot = info.get("vs_bot") if isinstance(info.get("vs_bot"), dict) else {}
            win = vs_bot.get("win")
            ok = isinstance(win, (int, float)) and not isinstance(win, bool)
            self.level_cells[lv, "win_vs_bot"].setText(pct(win, 0) if ok else "-")

        world = self.models.load_passport("world") or {}
        self._final = world.get("final") if isinstance(world.get("final"), dict) else {}
        self.world_label.setText(self._accuracy(self._final))
        self.chart_world_loss.set_points(points_from(world.get("curve"), "step", "loss"))
        self.chart_world_field.set_points(points_from(world.get("curve"), "step", "field"))
        self.chart_imitation.set_points(points_from(player.get("imitation_curve"), "step",
                                                    "accuracy"))
        self.chart_rl.set_points(points_from(player.get("rl_curve"), "episode", "reward"))
        designer = self.models.load_passport("designer") or {}
        painter = self.models.load_passport("painter") or {}
        self.chart_designer.set_points(points_from(designer.get("curve"), "step", "px"))
        self.chart_painter.set_points(points_from(painter.get("curve"), "step", "diff"))
        self._design = (designer.get("final") if isinstance(designer.get("final"), dict) else {},
                        painter.get("final") if isinstance(painter.get("final"), dict) else {},
                        self.journal.data if self.journal is not None else None)
        self.design_label.setText(self._design_text(*self._design))
        self.no_charts.setVisible(self.visible_charts() == 0)

    def _design_text(self, designer, painter, journal):
        t, c = self.t, self.colors

        def num(v):
            return isinstance(v, (int, float)) and not isinstance(v, bool)

        def b(text, good=True):
            return f"<b style='color:{c['good'] if good else c['mid']}'>{text}</b>"
        lines = []
        if journal is not None:
            n = journal.get("deviation_n", 0)
            if n:
                lines.append(t("design_deviation", px=b(f"{journal['deviation_sum'] / n:.1f}")))
            else:
                lines.append(t("design_deviation_none"))
            lines.append(t("design_layouts", net=b(journal.get("layouts", 0)),
                           code=b(journal.get("layout_fallbacks", 0), journal.get("layout_fallbacks", 0) == 0)))
            lines.append(t("design_tiles", net=b(journal.get("tile_sets", 0)),
                           code=b(journal.get("tile_fallbacks", 0), journal.get("tile_fallbacks", 0) == 0)))
        if num(designer.get("px_mean")) and num(designer.get("laws_pass")):
            lines.append(t("design_trained", px=b(f"{designer['px_mean']:.2f}"),
                           laws=b(pct(designer["laws_pass"]), designer["laws_pass"] >= 0.95)))
        if num(painter.get("diff_mean")) and num(painter.get("laws_pass")):
            lines.append(t("painter_trained", diff=b(pct(painter["diff_mean"])),
                           laws=b(pct(painter["laws_pass"]), painter["laws_pass"] >= 0.95)))
        if not lines:
            return f"<span style='color:{c['muted']}'>{t('design_none')}</span>"
        return "<br>".join(lines)

    def design_text(self):
        return self.design_label.text()

    def _accuracy(self, final):
        t, c = self.t, self.colors
        parts = []
        for key, goal, above in ACCURACY_ROWS:
            v = final.get(key)
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            ok = v >= goal if above else v < goal
            color = c["good"] if ok else c["mid"]
            sign = "≥" if above else "&lt;"            # это RichText: «<» открыл бы тег
            parts.append(f"{t('acc_' + key)}: <b style='color:{color}'>{v * 100:.2f}%</b> "
                         f"<span style='color:{c['muted']}'>({t('goal')} {sign} {goal * 100:g}%)</span>")
        if not parts:
            return f"<span style='color:{c['muted']}'>{t('no_world_passport')}</span>"
        return "<br>".join(parts)

    def elements(self):
        return [("title", self.title_label, None), ("back", self.back_button, None), ("scroll", self.scroll, None)]

    def accuracy_text(self):
        return self.world_label.text()

    def visible_charts(self):
        return sum(not c.isHidden() for c in self.charts)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.back.emit()
            return
        super().keyPressEvent(event)


# --- настройки ------------------------------------------------------------------------


class SettingsScreen(Screen):
    NAME = "settings"
    back = Signal()
    changed = Signal(str)

    def __init__(self, store, ctx, parent=None):
        super().__init__(parent)
        self.store = store
        self.ctx = ctx
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        self.track(outer)
        outer.addLayout(self.header("settings", self.back.emit))
        self.gap(outer, 10)

        # две карточки рядом на всё окно под заголовком - как прокрутка «Статистики»
        # (Алексей: в 1.1 настройки были прижаты в левый верхний угол)
        cards = QHBoxLayout()
        cards.setSpacing(14)
        self.track(cards)
        self.card_game, game_box, self.game_head = self._card("card_game")
        self.card_view, view_box, self.view_head = self._card("card_view")
        cards.addWidget(self.card_game, 1)
        cards.addWidget(self.card_view, 1)
        outer.addLayout(cards, 1)

        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(*st.SPEED_RANGE)
        self.speed.setSingleStep(5)
        self.speed.setPageStep(10)
        self.speed_value = label("", "value")
        self.row_speed = self._row(game_box, "speed", self.speed, self.speed_value, "speed_hint")

        self.opponent = QComboBox()
        for lv in st.LEVELS:
            self.opponent.addItem(lv, lv)
        self.row_opponent = self._row(game_box, "opponent", self.opponent, None, "opponent_hint")

        self.food_map = self.texts.add(QCheckBox(), "food_map_box")
        self.row_food_map = self._row(game_box, "food_map", self.food_map, None, "food_map_hint")
        game_box.addStretch(1)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(*st.VOLUME_RANGE)
        self.volume_value = label("", "value")
        self.row_volume = self._row(view_box, "volume", self.volume, self.volume_value, None)

        self.theme_combo = QComboBox()
        for name in theme.THEMES:
            self.theme_combo.addItem(name, name)
        self.row_theme = self._row(view_box, "theme", self.theme_combo, None, None)

        self.lang_combo = QComboBox()
        for key, text in LANG_NAMES.items():
            self.lang_combo.addItem(text, key)
        self.row_language = self._row(view_box, "language", self.lang_combo, None, None)

        self.palette = QComboBox()
        for i in range(len(PALETTES)):
            self.palette.addItem(PALETTES[i]["name"])
        self.preview = mini_board()
        self.row_palette = self._row(view_box, "field_colors", self.palette, None, None, extra=self.preview)
        view_box.addStretch(1)

        self.speed.valueChanged.connect(lambda v: self._set("speed_ms", v))
        self.opponent.currentIndexChanged.connect(
            lambda i: self._set("opponent", self.opponent.itemData(i)))
        self.volume.valueChanged.connect(self._set_volume)
        self.volume.sliderReleased.connect(lambda: self.changed.emit("sound_check"))
        self.theme_combo.currentIndexChanged.connect(lambda i: ctx.set_theme(self.theme_combo.itemData(i)))
        self.lang_combo.currentIndexChanged.connect(lambda i: ctx.set_lang(self.lang_combo.itemData(i)))
        self.palette.currentIndexChanged.connect(lambda i: self._set("palette", i))
        self.food_map.toggled.connect(lambda on: self._set("show_food_map", bool(on)))

    def _card(self, head_key):
        c = card()
        box = QVBoxLayout(c)
        box.setContentsMargins(24, 20, 24, 20)
        box.setSpacing(18)
        self.track(box)
        head = self.texts.add(label("", "section"), head_key, upper=True)
        box.addWidget(head)
        return c, box, head

    def _row(self, box, name_key, widget, value, hint_key, extra=None):
        """Строка настройки - свой виджет: подпись, элемент (и число справа), подсказка."""
        row = QWidget()
        col = QVBoxLayout(row)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        self.track(col)
        col.addWidget(self.texts.add(label("", "value"), name_key))
        line = QHBoxLayout()
        line.addWidget(widget, 1 if isinstance(widget, QSlider) else 0)
        if value is not None:
            value.setMinimumWidth(110)
            line.addWidget(value)
        if not isinstance(widget, QSlider):
            line.addStretch(1)
        col.addLayout(line)
        if extra is not None:
            col.addWidget(extra, 0, Qt.AlignmentFlag.AlignLeft)
        if hint_key:
            col.addWidget(self.texts.add(HintLabel(), hint_key))
        box.addWidget(row)
        return row

    def elements(self):
        return [("title", self.title_label, None), ("back", self.back_button, None),
                ("card_game", self.card_game, None), ("game_head", self.game_head, "card_game"),
                ("row_speed", self.row_speed, "card_game"), ("row_opponent", self.row_opponent, "card_game"),
                ("row_food_map", self.row_food_map, "card_game"),
                ("card_view", self.card_view, None), ("view_head", self.view_head, "card_view"),
                ("row_volume", self.row_volume, "card_view"), ("row_theme", self.row_theme, "card_view"),
                ("row_language", self.row_language, "card_view"), ("row_palette", self.row_palette, "card_view")]

    def design_layouts(self):
        return [self.layout(), self.card_game.layout(), self.card_view.layout()]

    def retranslate(self, t):
        super().retranslate(t)
        for i, lv in enumerate(st.LEVELS):
            self.opponent.setItemText(i, t("level_" + lv))
        for i, name in enumerate(theme.THEMES):
            self.theme_combo.setItemText(i, t("theme_" + name))
        for i in range(len(PALETTES)):
            self.palette.setItemText(i, t(f"palette_{i}"))
        self._labels()

    def load(self):
        """Показать сохранённые значения, ничего не записывая."""
        s = self.store.settings
        widgets = (self.speed, self.opponent, self.volume, self.palette, self.food_map,
                   self.theme_combo, self.lang_combo)
        for w in widgets:
            w.blockSignals(True)
        self.speed.setValue(s["speed_ms"])
        self.opponent.setCurrentIndex(st.LEVELS.index(s["opponent"]))
        self.volume.setValue(self.ctx.sound.volume)
        self.palette.setCurrentIndex(s["palette"])
        self.food_map.setChecked(s["show_food_map"])
        self.theme_combo.setCurrentIndex(list(theme.THEMES).index(self.ctx.theme))
        self.lang_combo.setCurrentIndex(list(LANG_NAMES).index(self.ctx.lang))
        for w in widgets:
            w.blockSignals(False)
        self._labels()

    def _labels(self):
        s = self.store.settings
        self.speed_value.setText(self.t("speed_value", ms=s["speed_ms"]))
        self.volume_value.setText(f"{self.ctx.sound.volume}%")
        self.preview.set_palette(s["palette"])

    def _set(self, key, value):
        self.store.set(key, value)
        self._labels()
        self.changed.emit(key)

    def _set_volume(self, value):
        self.ctx.set_volume(value)          # громкость общая: в ctx, оттуда - оболочке
        self._labels()
        self.changed.emit("volume")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.back.emit()
            return
        super().keyPressEvent(event)
