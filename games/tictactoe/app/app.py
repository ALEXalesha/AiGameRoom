"""Окно игры: меню, партия, статистика, настройки. Интерфейс на русском."""
import os

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractItemView, QButtonGroup, QCheckBox, QComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QHeaderView, QLabel, QMainWindow,
                               QPushButton, QScrollArea, QSlider, QStackedWidget,
                               QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

from games.tictactoe import paths
from games.tictactoe.core import rules
from games.tictactoe.app import models, theme
from games.tictactoe.app.board_widget import BoardWidget
from games.tictactoe.app.chart import CurveChart
from games.tictactoe.app.icon import app_icon
from games.tictactoe.app.session import Session
from games.tictactoe.app.settings import Settings
from games.tictactoe.app.sound import Sounds
from games.tictactoe.app.stats import Stats
from games.tictactoe.app.version import VERSION
from games.tictactoe.app.window_state import WindowMemory

TITLE = "Крестики-нолики с нейросетью"
FIRST_NAMES = {"me": "Я", "net": "Сеть", "alternate": "По очереди"}
FIELD_NAMES = {3: "3×3", 5: "5×5"}
FIELD_RULES = {3: "три в ряд", 5: "четыре в ряд"}
WINDOW_OPTS = {"width": 1000, "height": 700, "minWidth": 780, "minHeight": 560}


def plural(n, one, few, many):
    n = abs(n)
    if n % 10 == 1 and n % 100 != 11:
        return one
    if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
        return few
    return many


def label(text, name=None, wrap=False):
    w = QLabel(text)
    if name:
        w.setObjectName(name)
    w.setWordWrap(wrap)
    return w


def card():
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def button(text, name=None, slot=None):
    b = QPushButton(text)
    if name:
        b.setObjectName(name)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if slot:
        b.clicked.connect(slot)
    return b


class Page(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def on_show(self):
        self.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape and self.window_.current_page() != "menu":
            self.window_.show_page("menu")
            return
        super().keyPressEvent(event)


def segmented(options, slot):
    """Ряд кнопок-переключателей: {значение: подпись}. Возвращает (виджет, {значение: кнопка})."""
    box = QWidget()
    row = QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(6)
    group = QButtonGroup(box)
    group.setExclusive(True)
    buttons = {}
    for value, text in options.items():
        b = button(text, "seg")
        b.setCheckable(True)
        b.clicked.connect(lambda _=False, v=value: slot(v))
        group.addButton(b)
        row.addWidget(b)
        buttons[value] = b
    return box, buttons


# --- меню ---


class Logo(QWidget):
    """Маленькое поле с законченной партией - картинка над заголовком меню."""

    def __init__(self):
        super().__init__()
        self.setFixedSize(150, 150)
        self.colors = theme.palette("dark")

    def paintEvent(self, event):
        from games.tictactoe.app.icon import render
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.drawImage(QRectF(0, 0, self.width(), self.height()), render(300))
        p.end()


class MenuPage(Page):
    def __init__(self, window):
        super().__init__(window)
        outer = QVBoxLayout(self)
        outer.addStretch(3)
        col = QVBoxLayout()
        col.setSpacing(10)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        logo = Logo()
        col.addWidget(logo, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(8)
        title = label("Крестики-нолики", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(title)
        sub = label("против нейросети, которая научилась играть сама", "muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(sub)
        col.addSpacing(22)
        self.play_button = button("Играть", "menuPrimary", lambda: window.start_play())
        self.stats_button = button("Статистика", "menu", lambda: window.show_page("stats"))
        self.settings_button = button("Настройки", "menu", lambda: window.show_page("settings"))
        self.quit_button = button("Выход", "menu", window.close)
        for b in (self.play_button, self.stats_button, self.settings_button, self.quit_button):
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addLayout(col)
        outer.addStretch(4)
        foot = label(f"версия {VERSION} · поля 3×3 и 5×5 · сеть на numpy, без готовых библиотек", "hint")
        foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(foot)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.window_.start_play()
            return
        super().keyPressEvent(event)


# --- партия ---


class GamePage(Page):
    def __init__(self, window):
        super().__init__(window)
        self.session = None
        self.token = 0
        s = window.settings
        self.size, self.level, self.first = s.size, s.level, s.first

        root = QHBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(24)
        self.board_widget = BoardWidget()
        self.board_widget.cellClicked.connect(self.on_cell)
        root.addWidget(self.board_widget, 1)

        side = card()
        side.setFixedWidth(300)
        col = QVBoxLayout(side)
        col.setContentsMargins(18, 16, 18, 16)
        col.setSpacing(6)

        col.addWidget(label("Поле", "muted"))
        box, self.size_buttons = segmented({3: "3×3", 5: "5×5"}, self.set_size)
        col.addWidget(box)
        col.addSpacing(4)
        col.addWidget(label("Уровень сети", "muted"))
        box, self.level_buttons = segmented(dict(models.LEVEL_NAMES), self.set_level)
        col.addWidget(box)
        col.addSpacing(4)
        col.addWidget(label("Первый ход", "muted"))
        self.first_combo = QComboBox()
        self.first_combo.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        for key, text in FIRST_NAMES.items():
            self.first_combo.addItem(text, key)
        self.first_combo.currentIndexChanged.connect(
            lambda i: self.set_first(self.first_combo.itemData(i)))
        col.addWidget(self.first_combo)

        col.addSpacing(8)

        self.status = label("", "status")
        col.addWidget(self.status)
        self.substatus = label("", "muted", wrap=True)
        # не меньше двух строк: текст меняется по ходу партии, а панель не должна прыгать.
        # Но и не больше нельзя: фиксированная высота обрезала перенесённый текст (26.09).
        self.substatus.setMinimumHeight(40)
        self.substatus.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        col.addWidget(self.substatus)
        col.addSpacing(4)

        score = QHBoxLayout()
        score.setSpacing(6)
        self.score_labels = {}
        for key, text in (("wins", "победы"), ("draws", "ничьи"), ("losses", "поражения")):
            cell = QVBoxLayout()
            cell.setSpacing(0)
            num = label("0", "bigNumber")
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cap = label(text, "hint")
            cap.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cell.addWidget(num)
            cell.addWidget(cap)
            score.addLayout(cell)
            self.score_labels[key] = num
        col.addLayout(score)
        self.score_caption = label("", "hint", wrap=True)
        self.score_caption.setMinimumHeight(18)
        self.score_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.score_caption)
        col.addSpacing(4)

        self.thoughts_box = QCheckBox("Мысли сети")
        self.thoughts_box.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.thoughts_box.setChecked(s.show_thoughts)
        self.thoughts_box.toggled.connect(lambda on: window.change_setting("show_thoughts", on))
        col.addWidget(self.thoughts_box)
        self.thoughts_hint = label("Оценка клеток для того, чья очередь: +1 - победа, −1 - поражение",
                                   "hint", wrap=True)
        col.addWidget(self.thoughts_hint)
        col.addStretch(1)

        self.again_button = button("Ещё раз", "primary", self.again)
        self.menu_button = button("В меню", None, lambda: window.show_page("menu"))
        col.addWidget(self.again_button)
        col.addWidget(self.menu_button)
        self.keys_hint = label("", "hint", wrap=True)
        # Высота - от текста: на настоящем экране фраза шире, чем в offscreen, переносится
        # на вторую строку, и высота в одну строку её обрезала (Алексей, 26.09.2026).
        self.keys_hint.setMinimumHeight(18)
        self.keys_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.keys_hint)
        root.addWidget(side)
        self.sync_controls()

    # --- выбор партии ---

    def sync_controls(self):
        self.size_buttons[self.size].setChecked(True)
        self.level_buttons[self.level].setChecked(True)
        self.first_combo.blockSignals(True)
        self.first_combo.setCurrentIndex(list(FIRST_NAMES).index(self.first))
        self.first_combo.blockSignals(False)

    def set_size(self, size):
        self.size = size
        self.window_.change_setting("size", size)
        self.new_session()

    def set_level(self, level):
        self.level = level
        self.window_.change_setting("level", level)
        self.new_session()

    def set_first(self, first):
        self.first = first
        self.new_session()

    def new_session(self):
        self.sync_controls()
        w = self.window_
        self.session = Session(self.size, self.level, models.load(self.size, self.level), first=self.first,
                               stats=w.stats, stats_path=w.stats_path)
        self.after_change()

    def again(self):
        if self.session is None:
            self.new_session()
            return
        self.session.restart()
        self.after_change()

    # --- ходы ---

    def on_cell(self, r, c):
        if self.session is not None and self.session.human_move((r, c)):
            self.after_move()

    def keyPressEvent(self, event):
        key = event.key()
        if self.session is not None and self.size == 3 and Qt.Key.Key_1 <= key <= Qt.Key.Key_9:
            self.on_cell(*divmod(key - Qt.Key.Key_1, 3))
            return
        if key in (Qt.Key.Key_R, Qt.Key.Key_F2):
            self.again()
            return
        super().keyPressEvent(event)

    def after_move(self):
        s = self.session
        if s.result is None:
            self.window_.sounds.play("x" if s.board[s.last] == rules.X else "o")
        else:
            self.window_.sounds.play(s.outcome_for_human())
        self.after_change()

    def after_change(self):
        self.token += 1
        self.refresh()
        s = self.session
        if s.result is None and not s.human_turn():
            token = self.token
            QTimer.singleShot(self.window_.settings.delay_ms, lambda: self.net_turn(token))

    def net_turn(self, token):
        s = self.session
        if token != self.token or s.result is not None or s.human_turn():
            return
        s.net_move()
        self.after_move()

    # --- вид ---

    def refresh(self):
        s = self.session
        if s is None:
            return
        show = self.window_.settings.show_thoughts
        self.board_widget.set_state(s.board, s.line, s.last, s.thoughts() if show and s.result is None else None,
                                    interactive=s.human_turn())
        mark = "крестиками (X)" if s.human == rules.X else "ноликами (O)"
        outcome = s.outcome_for_human()
        if outcome is None:
            self.status.setObjectName("status")
            self.status.setText("Ваш ход" if s.human_turn() else "Сеть думает…")
            self.substatus.setText(f"Вы играете {mark}, нужно {FIELD_RULES[s.size]}. "
                                   f"Сеть: {models.LEVEL_NAMES[s.level]}.")
        else:
            names = {"win": ("Победа!", "statusWin"), "loss": ("Поражение", "statusLoss"),
                     "draw": ("Ничья", "statusDraw")}
            text, obj = names[outcome]
            self.status.setObjectName(obj)
            self.status.setText(text)
            tail = {"win": "Вы обыграли сеть.", "loss": "Сеть собрала линию.",
                    "draw": "Поле заполнено, линии нет ни у кого."}[outcome]
            self.substatus.setText(f"{tail} Вы играли {mark}.")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)
        e = self.window_.stats.entry(s.size, s.level)
        for key, w in self.score_labels.items():
            w.setText(str(e[key]))
        streak = e["streak"]
        self.score_caption.setText(
            f"{FIELD_NAMES[s.size]}, {models.LEVEL_NAMES[s.level]}: {e['games']} "
            f"{plural(e['games'], 'партия', 'партии', 'партий')}"
            + (f", серия побед {streak}" if streak > 1 else ""))
        self.keys_hint.setText("Мышь или цифры 1–9 · R - ещё раз · Esc - меню" if s.size == 3
                               else "Ход мышью · R - ещё раз · Esc - меню")
        self.thoughts_box.blockSignals(True)
        self.thoughts_box.setChecked(show)
        self.thoughts_box.blockSignals(False)

    def apply_theme(self, name):
        self.board_widget.set_theme(name)


# --- статистика ---


def table(headers):
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.verticalHeader().setVisible(False)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
    t.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    t.setShowGrid(False)
    t.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    t.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    header = t.horizontalHeader()
    header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
    header.setHighlightSections(False)
    return t


def fit_height(t):
    t.resizeRowsToContents()
    h = t.horizontalHeader().height() + sum(t.rowHeight(r) for r in range(t.rowCount())) + 4
    t.setFixedHeight(h)


def item(text, align=Qt.AlignmentFlag.AlignCenter, color=None):
    it = QTableWidgetItem(text)
    it.setTextAlignment(align | Qt.AlignmentFlag.AlignVCenter)
    if color:
        it.setForeground(QColor(color))
    return it


def number(n):
    """12345 -> '12 345': разряды через неразрывный пробел, как принято по-русски."""
    return f"{n:,}".replace(",", " ")


def check_text(c):
    return f"{round(100 * c['win_rate'])}%   {c['wins']} / {c['draws']} / {c['losses']}"


class StatsPage(Page):
    def __init__(self, window):
        super().__init__(window)
        self.field = 3
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        body = QWidget()
        body.setObjectName("page")
        body.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        scroll.setWidget(body)
        col = QVBoxLayout(body)
        col.setContentsMargins(28, 24, 28, 24)
        col.setSpacing(16)

        top = QHBoxLayout()
        top.addWidget(label("Статистика", "heading"))
        top.addStretch(1)
        top.addWidget(button("В меню", None, lambda: window.show_page("menu")))
        col.addLayout(top)

        # ваши партии
        mine = card()
        mc = QVBoxLayout(mine)
        mc.setContentsMargins(20, 16, 20, 16)
        mc.setSpacing(10)
        mc.addWidget(label("Ваши партии", "section"))
        totals = QHBoxLayout()
        self.total_labels = {}
        for key, text in (("games", "партий"), ("wins", "побед"), ("draws", "ничьих"),
                          ("losses", "поражений"), ("best_streak", "лучшая серия побед")):
            cell = QVBoxLayout()
            cell.setSpacing(0)
            num = label("0", "bigNumber")
            cap = label(text, "hint")
            cell.addWidget(num)
            cell.addWidget(cap)
            totals.addLayout(cell)
            self.total_labels[key] = num
        totals.addStretch(1)
        mc.addLayout(totals)
        self.table = table(["Поле и уровень сети", "Партии", "Победы", "Поражения", "Ничьи",
                            "Серия", "Лучшая серия"])
        mc.addWidget(self.table)
        col.addWidget(mine)

        # обучение
        learn = card()
        lc = QVBoxLayout(learn)
        lc.setContentsMargins(20, 16, 20, 16)
        lc.setSpacing(10)
        head = QHBoxLayout()
        head.addWidget(label("Как сеть училась", "section"))
        head.addStretch(1)
        box, self.field_buttons = segmented({3: "3×3", 5: "5×5"}, self.set_field)
        head.addWidget(box)
        lc.addLayout(head)
        self.learn_caption = label("", "muted", wrap=True)
        lc.addWidget(self.learn_caption)
        self.chart = CurveChart()
        lc.addWidget(self.chart)
        lc.addWidget(label("Проверки сети", "section"))
        self.checks = table(["Уровень", "Партий обучения", "Против случайного", "Против бота",
                             "Против минимакса"])
        lc.addWidget(self.checks)
        self.checks_caption = label("", "hint", wrap=True)
        lc.addWidget(self.checks_caption)
        col.addWidget(learn)
        col.addStretch(1)

    def on_show(self):
        super().on_show()
        self.refresh()

    def set_field(self, size):
        self.field = size
        self.refresh()

    def refresh(self):
        stats = self.window_.stats
        tot = stats.totals()
        for key, w in self.total_labels.items():
            w.setText(str(tot[key]))
        rows = [(size, level) for size in (3, 5) for level in models.LEVELS]
        self.table.setRowCount(len(rows))
        for r, (size, level) in enumerate(rows):
            e = stats.entry(size, level)
            self.table.setItem(r, 0, item(f"{FIELD_NAMES[size]} · {models.LEVEL_NAMES[level]}",
                                          Qt.AlignmentFlag.AlignLeft))
            for c, key in enumerate(("games", "wins", "losses", "draws", "streak", "best_streak"), start=1):
                self.table.setItem(r, c, item(str(e[key])))
        fit_height(self.table)

        self.field_buttons[self.field].setChecked(True)
        pp = models.passport(self.field)
        marks = [(lv["games"], lv["name"]) for lv in pp["levels"] if lv["key"] != "strong"]
        self.chart.set_data(pp["curve"], marks)
        net = pp["network"]
        kind = ("плотная сеть 18 → {h} → {h} → 1".format(h=net["hidden"]) if net["kind"] == "dense" else
                "свёртки 3×3 (2 → " + " → ".join([str(net["channels"])] * net["conv_layers"]) + ")"
                + (f", плотный слой {net['head']} → 1" if net.get("head") else " → 1"))
        sec = pp["train_seconds"]
        took = f"{round(sec)} с" if sec < 90 else f"{round(sec / 60)} мин"
        self.learn_caption.setText(
            f"Поле {FIELD_NAMES[self.field]}, {FIELD_RULES[self.field]}. Сеть: {kind}, "
            f"{number(net['parameters'])} весов. Она сыграла сама с собой {number(pp['games'])} партий "
            f"за {took}; ни одной стратегии ей не давали. "
            "Линии - доля побед сети по ходу обучения, пунктир - где сняты уровни.")
        self.checks.setRowCount(len(pp["levels"]))
        minimax = self.field == 3
        self.checks.setColumnHidden(4, not minimax)
        for r, lv in enumerate(pp["levels"]):
            ch = lv["checks"]
            self.checks.setItem(r, 0, item(lv["name"], Qt.AlignmentFlag.AlignLeft))
            self.checks.setItem(r, 1, item(number(lv["games"])))
            self.checks.setItem(r, 2, item(check_text(ch["vs_random"])))
            self.checks.setItem(r, 3, item(check_text(ch["vs_bot"])))
            if minimax:
                mm = ch["vs_minimax"]
                good = self.window_.colors()["good" if mm["losses"] == 0 else "bad"]
                self.checks.setItem(r, 4, item(check_text(mm), color=good))
        fit_height(self.checks)
        games = pp["levels"][-1]["checks"]["vs_random"]["games"]
        text = (f"По {games} партий на проверку, половину сеть ходит первой. Числа: доля побед, "
                "затем победы / ничьи / поражения. Бот «выиграй или помешай» смотрит на ход вперёд.")
        if minimax:
            text += " Минимакс перебирает всю игру и не проигрывает никогда."
            safe = [lv["name"] for lv in pp["levels"]
                    if min(lv["checks"].get("worst_case", {"x": -1}).values()) >= 0]
            if safe:
                text += (" Полным перебором всех ходов соперника проверено: уровень «"
                         + "», «".join(safe) + "» не проигрывает никому, ни крестиками, ни ноликами.")
        self.checks_caption.setText(text)

    def apply_theme(self, name):
        self.chart.set_theme(name)
        if self.isVisible():
            self.refresh()


# --- настройки ---


class SettingsPage(Page):
    def __init__(self, window):
        super().__init__(window)
        s = window.settings
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 24, 28, 24)
        outer.setSpacing(16)
        top = QHBoxLayout()
        top.addWidget(label("Настройки", "heading"))
        top.addStretch(1)
        top.addWidget(button("В меню", None, lambda: window.show_page("menu")))
        outer.addLayout(top)

        box = card()
        box.setMaximumWidth(720)
        grid = QGridLayout(box)
        grid.setContentsMargins(24, 20, 24, 20)
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(18)
        grid.setColumnStretch(1, 1)

        def row(r, title, hint, widget, extra=None):
            names = QVBoxLayout()
            names.setSpacing(2)
            names.addWidget(label(title, "section"))
            names.addWidget(label(hint, "hint", wrap=True))
            grid.addLayout(names, r, 0)
            line = QHBoxLayout()
            line.addWidget(widget, 1)
            if extra is not None:
                line.addWidget(extra)
            grid.addLayout(line, r, 1)

        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(s.volume)
        self.volume_label = label(f"{s.volume}%")
        self.volume_label.setMinimumWidth(56)
        self.volume.valueChanged.connect(self.on_volume)
        row(0, "Громкость", "Звуки ходов и конца партии", self.volume, self.volume_label)

        self.theme_combo = QComboBox()
        for key, text in theme.THEME_NAMES.items():
            self.theme_combo.addItem(text, key)
        self.theme_combo.setCurrentIndex(list(theme.THEME_NAMES).index(s.theme))
        self.theme_combo.currentIndexChanged.connect(
            lambda i: window.change_setting("theme", self.theme_combo.itemData(i)))
        row(1, "Тема", "Тёмная или светлая", self.theme_combo)

        self.delay = QSlider(Qt.Orientation.Horizontal)
        self.delay.setRange(0, 2000)
        self.delay.setSingleStep(50)
        self.delay.setPageStep(250)
        self.delay.setValue(s.delay_ms)
        self.delay_label = label(self.delay_text(s.delay_ms))
        self.delay_label.setMinimumWidth(56)
        self.delay.valueChanged.connect(self.on_delay)
        row(2, "Задержка хода сети", "Пауза перед ходом, чтобы его было видно", self.delay, self.delay_label)

        self.thoughts = QCheckBox("Показывать")
        self.thoughts.setChecked(s.show_thoughts)
        self.thoughts.toggled.connect(lambda on: window.change_setting("show_thoughts", on))
        row(3, "Мысли сети", "Оценка каждой свободной клетки цветом и числом", self.thoughts)

        self.first_combo = QComboBox()
        for key, text in FIRST_NAMES.items():
            self.first_combo.addItem(text, key)
        self.first_combo.setCurrentIndex(list(FIRST_NAMES).index(s.first))
        self.first_combo.currentIndexChanged.connect(
            lambda i: window.change_setting("first", self.first_combo.itemData(i)))
        row(4, "Первый ход по умолчанию", "Кто ходит первым, когда нажато «Играть»", self.first_combo)

        outer.addWidget(box)
        outer.addWidget(label("Всё сохраняется сразу.", "hint"))
        outer.addStretch(1)

    @staticmethod
    def delay_text(ms):
        return f"{ms / 1000:.2f} с".replace(".", ",")

    def on_volume(self, v):
        self.volume_label.setText(f"{v}%")
        self.window_.change_setting("volume", v)

    def on_delay(self, v):
        v = int(round(v / 50) * 50)
        self.delay_label.setText(self.delay_text(v))
        self.window_.change_setting("delay_ms", v)

    def sync(self):
        s = self.window_.settings
        for w, value in ((self.volume, s.volume), (self.delay, s.delay_ms)):
            w.blockSignals(True)
            w.setValue(value)
            w.blockSignals(False)
        self.volume_label.setText(f"{s.volume}%")
        self.delay_label.setText(self.delay_text(s.delay_ms))
        self.thoughts.blockSignals(True)
        self.thoughts.setChecked(s.show_thoughts)
        self.thoughts.blockSignals(False)
        self.sync_combos()

    def on_show(self):
        super().on_show()
        self.sync()

    def sync_combos(self):
        s = self.window_.settings
        for combo, keys, value in ((self.theme_combo, list(theme.THEME_NAMES), s.theme),
                                   (self.first_combo, list(FIRST_NAMES), s.first)):
            combo.blockSignals(True)
            combo.setCurrentIndex(keys.index(value))
            combo.blockSignals(False)


# --- окно ---


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.settings_path = paths.user_file("settings.json")
        self.stats_path = paths.user_file("stats.json")
        self.settings = Settings.load(self.settings_path)
        self.stats = Stats.load(self.stats_path)
        self.sounds = Sounds(os.path.join(paths.data_dir(), "sounds"), self.settings.volume)

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.menu = MenuPage(self)
        self.game = GamePage(self)
        self.stats_page = StatsPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = {"menu": self.menu, "game": self.game, "stats": self.stats_page,
                      "settings": self.settings_page}
        for page in self.pages.values():
            self.stack.addWidget(page)
        self.apply_theme(self.settings.theme)
        self.game.new_session()
        # меньше, чем нужно панели партии, окно не сжимается: иначе строки налезают друг на
        # друга. Размер известен только после стилей - шрифты и отступы задаёт тема.
        need = self.stack.minimumSizeHint()
        self.window_opts = {**WINDOW_OPTS, "minWidth": max(WINDOW_OPTS["minWidth"], need.width()),
                            "minHeight": max(WINDOW_OPTS["minHeight"], need.height())}
        self.setMinimumSize(self.window_opts["minWidth"], self.window_opts["minHeight"])
        self.memory = WindowMemory(self, paths.user_file("window.json"), self.window_opts)
        self.show_page("menu")

    def colors(self):
        return theme.palette(self.settings.theme)

    def current_page(self):
        current = self.stack.currentWidget()
        return next(name for name, page in self.pages.items() if page is current)

    def show_page(self, name):
        if name != "game":
            self.game.token += 1          # ход сети, ждущий в таймере, больше не нужен
        self.stack.setCurrentWidget(self.pages[name])
        self.pages[name].on_show()
        if name == "game" and self.game.session is None:
            self.game.new_session()

    def start_play(self):
        """«Играть» из меню: первый ход - из настроек, поле и уровень - последние выбранные."""
        self.game.first = self.settings.first
        self.stack.setCurrentWidget(self.game)
        self.game.on_show()
        self.game.new_session()

    def change_setting(self, name, value):
        setattr(self.settings, name, value)
        self.settings.save(self.settings_path)
        if name == "theme":
            self.apply_theme(value)
        elif name == "volume":
            self.sounds.set_volume(value)
        elif name == "show_thoughts":
            self.game.refresh()

    def apply_theme(self, name):
        self.setStyleSheet(theme.qss(name))
        for page in self.pages.values():
            if hasattr(page, "apply_theme"):
                page.apply_theme(name)

    # место окна
    def moveEvent(self, event):
        super().moveEvent(event)
        self.memory.track() if hasattr(self, "memory") else None

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.memory.track() if hasattr(self, "memory") else None

    def closeEvent(self, event):
        self.game.token += 1
        self.memory.save()
        self.settings.save(self.settings_path)
        super().closeEvent(event)


def run(argv=None):
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(argv or [])
    app.setApplicationName("TicTacToeAi")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.memory.show()
    return app.exec()
