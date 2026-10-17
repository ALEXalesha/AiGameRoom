"""Виджет игры (create_widget по контракту): меню, матч, статистика, настройки.

Окно ему даёт оболочка (aikit.run_standalone или ИИ-Игротека). Тема и язык приходят из
ctx и меняются на лету по ctx.changed. Файлы - только в ctx.data_dir.

ИИ считает ход за миллисекунды, поэтому своих потоков у игры нет: есть только таймер
показа «ИИ против бота», и shutdown() его останавливает.
"""
import os
import random

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (QAbstractItemView, QCheckBox, QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLayout,
                               QListWidget, QScrollArea, QSlider, QStackedWidget, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from aikit import settings as st
from aikit import gamelog, theme
from aikit.charts import BarChart, LineChart
from aikit.storage import load_json, save_json
from aikit.widgets import Combo, button, card, label, restyle, segmented
from games.rockpaper.ai.bots import BOTS
from games.rockpaper.ai.habits import analyse, caught_at
from games.rockpaper.ai.player import LEVELS
from games.rockpaper.core.rules import LOSS, NAMES, WIN
from games.rockpaper.ui.i18n import translator
from games.rockpaper.ui.session import Session
from games.rockpaper.ui.views import ProbBars, ShareChart, SignButton
from games.rockpaper.version import VERSION

DEMO_BOTS = ("cycle", "repeat", "wsls", "markov2", "biased", "human", "random", "mirror")
SCHEMA = {
    "k": (3, st.choice(3, 5)),
    "length": (100, st.choice(50, 100, 0)),
    "level": ("strong", st.choice(*LEVELS)),
    "mode": ("play", st.choice("play", "demo")),
    "bot": ("human", st.choice(*DEMO_BOTS)),
    "show_thoughts": (True, st.boolean()),
    "peek": (False, st.boolean()),
    "delay_ms": (500, st.int_range(0, 3000)),
}
MAX_HISTORY = 500
PASSPORT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models", "rockpaper-passport.json")


def page_widget():
    w = QWidget()
    w.setObjectName("page")
    w.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
    return w


def scroll_of(body):
    s = QScrollArea()
    s.setWidgetResizable(True)
    s.setFrameShape(QFrame.Shape.NoFrame)
    s.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    s.setWidget(body)
    return s


def pct(v):
    return round(v * 100)


def predictor_name(t, key, params):
    n = params.get("n", 0)
    return t("p_" + key, n=n) if "{n}" in t("p_" + key) else t("p_" + key)


# --- меню ---


class MenuPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        outer = QVBoxLayout(self)
        outer.addStretch(2)
        col = QVBoxLayout()
        col.setSpacing(10)
        col.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        from PySide6.QtGui import QPixmap
        from PySide6.QtWidgets import QLabel
        from games.rockpaper.ui.glyphs import render_icon
        self.logo = QLabel()
        self.logo.setPixmap(QPixmap.fromImage(render_icon(104)))
        col.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.title = label("", "title")
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col.addWidget(self.title)
        self.sub = label("", "muted", wrap=True)
        self.sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sub.setFixedWidth(640)
        col.addWidget(self.sub, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(10)
        box = card()
        box.setMaximumWidth(700)
        grid = QGridLayout(box)
        grid.setContentsMargins(22, 18, 22, 18)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)
        self.captions = {}

        def row(r, key, widget):
            cap = label("", "muted")
            self.captions[key] = cap
            grid.addWidget(cap, r, 0)
            grid.addWidget(widget, r, 1)

        w, self.k_buttons = segmented({3: "", 5: ""}, lambda v: gw.change("k", v))
        row(0, "variant", w)
        w, self.len_buttons = segmented({50: "", 100: "", 0: ""}, lambda v: gw.change("length", v))
        row(1, "length", w)
        w, self.level_buttons = segmented({lv: "" for lv in LEVELS}, lambda v: gw.change("level", v))
        row(2, "level", w)
        w, self.mode_buttons = segmented({"play": "", "demo": ""}, lambda v: gw.change("mode", v))
        row(3, "mode", w)
        self.bot_combo = Combo()
        for b in DEMO_BOTS:
            self.bot_combo.addItem("", b)
        self.bot_combo.currentIndexChanged.connect(lambda i: gw.change("bot", self.bot_combo.itemData(i)))
        row(4, "bot", self.bot_combo)
        col.addWidget(box, 0, Qt.AlignmentFlag.AlignHCenter)
        col.addSpacing(8)
        self.play_button = button("", "menuPrimary", lambda: gw.start_match())
        self.stats_button = button("", "menu", lambda: gw.show_page("stats"))
        self.settings_button = button("", "menu", lambda: gw.show_page("settings"))
        for b in (self.play_button, self.stats_button, self.settings_button):
            col.addWidget(b, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addLayout(col)
        outer.addStretch(3)
        self.foot = label("", "hint")
        self.foot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(self.foot)

    def sync(self, s):
        self.k_buttons[s["k"]].setChecked(True)
        self.len_buttons[s["length"]].setChecked(True)
        self.level_buttons[s["level"]].setChecked(True)
        self.mode_buttons[s["mode"]].setChecked(True)
        self.bot_combo.blockSignals(True)
        self.bot_combo.setCurrentIndex(self.bot_combo.findData(s["bot"]))
        self.bot_combo.blockSignals(False)
        # строка бота видна всегда (скрытая строка сетки сжимала карточку), но нужна только в показе
        self.bot_combo.setEnabled(s["mode"] == "demo")

    def retranslate(self):
        t = self.gw.t
        self.title.setText(t("app_title"))
        self.sub.setText(t("app_sub"))
        for key, cap in self.captions.items():
            cap.setText(t(key))
        self.k_buttons[3].setText(t("v3"))
        self.k_buttons[5].setText(t("v5"))
        for v, b in self.len_buttons.items():
            b.setText(t(f"len{v}"))
        for k, b in self.level_buttons.items():
            b.setText(t(k))
        for k, b in self.mode_buttons.items():
            b.setText(t("mode_" + k))
        for i, b in enumerate(DEMO_BOTS):
            self.bot_combo.setItemText(i, t("b_" + b))
        self.play_button.setText(t("play"))
        self.stats_button.setText(t("stats"))
        self.settings_button.setText(t("settings"))
        self.foot.setText(t("footer", v=VERSION))
        self.sync(self.gw.settings)


# --- матч ---


class PlayPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        self.setObjectName("page")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(14)

        body = page_widget()
        main = QVBoxLayout(body)
        main.setContentsMargins(0, 0, 6, 0)
        main.setSpacing(8)
        top = QHBoxLayout()
        self.heading = label("", "section", wrap=True)
        top.addWidget(self.heading, 1)
        self.round_label = label("", "muted")
        top.addWidget(self.round_label)
        main.addLayout(top)

        score = card()
        sg = QGridLayout(score)
        sg.setContentsMargins(18, 10, 18, 10)
        self.score_nums = []
        self.score_caps = []
        for i in range(3):
            n = label("0", "bigNumber")
            n.setAlignment(Qt.AlignmentFlag.AlignCenter)
            c = label("", "muted")
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sg.addWidget(n, 0, i)
            sg.addWidget(c, 1, i)
            self.score_nums.append(n)
            self.score_caps.append(c)
        main.addWidget(score)

        self.status = label("", "status", wrap=True)
        main.addWidget(self.status)
        self.not_counted = label("", None, wrap=True)
        main.addWidget(self.not_counted)
        self.commit = label("", "hint", wrap=True)
        main.addWidget(self.commit)
        signs = QHBoxLayout()
        signs.setSpacing(10)
        self.sign_buttons = []
        for i in range(5):
            b = SignButton(i)
            b.clicked.connect(gw.on_sign)
            signs.addWidget(b)
            self.sign_buttons.append(b)
        main.addLayout(signs)
        self.last = label("", "muted", wrap=True)
        main.addWidget(self.last)
        self.verify = label("", "hint", wrap=True)
        main.addWidget(self.verify)

        self.review = card()
        rv = QVBoxLayout(self.review)
        rv.setContentsMargins(18, 12, 18, 12)
        rv.setSpacing(6)
        self.review_title = label("", "section")
        self.review_text = label("", None, wrap=True)
        self.review_caught = label("", "muted", wrap=True)
        rv.addWidget(self.review_title)
        rv.addWidget(self.review_text)
        rv.addWidget(self.review_caught)
        main.addWidget(self.review)

        self.chart = ShareChart()
        main.addWidget(self.chart, 1)
        buttons = QHBoxLayout()
        self.new_button = button("", "primary", lambda: gw.start_match())
        self.end_button = button("", None, gw.end_match)
        self.pause_button = button("", None, gw.toggle_pause)
        self.menu_button = button("", None, lambda: gw.show_page("menu"))
        for b in (self.new_button, self.end_button, self.pause_button):
            buttons.addWidget(b)
        # Флажок подглядывания - здесь, а не в узкой боковой панели: длинная подпись не
        # переносится и раздвигала панель, обрезая подписи «Мыслей ИИ» справа.
        self.peek_box = QCheckBox("")
        self.peek_box.toggled.connect(lambda on: gw.change("peek", on))
        buttons.addSpacing(12)
        buttons.addWidget(self.peek_box)
        buttons.addStretch(1)
        buttons.addWidget(self.menu_button)
        main.addLayout(buttons)
        root.addWidget(scroll_of(body), 1)

        side = card()
        side.setFixedWidth(340)
        outer = QVBoxLayout(side)
        outer.setContentsMargins(0, 0, 0, 0)
        sbody = QWidget()
        sc = scroll_of(sbody)
        sc.setStyleSheet("QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; }")
        outer.addWidget(sc)
        col = QVBoxLayout(sbody)
        col.setContentsMargins(16, 14, 16, 14)
        col.setSpacing(6)
        self.thoughts_box = QCheckBox("")
        self.thoughts_box.toggled.connect(lambda on: gw.change("show_thoughts", on))
        col.addWidget(self.thoughts_box)
        self.thoughts_hint = label("", "hint", wrap=True)
        col.addWidget(self.thoughts_hint)
        self.th_title = label("", "section", wrap=True)
        col.addWidget(self.th_title)
        self.forecast_note = label("", None, wrap=True)
        col.addWidget(self.forecast_note)
        self.ai_move_peek = label("", "section", wrap=True)
        col.addWidget(self.ai_move_peek)
        self.bars_caption = label("", "muted", wrap=True)
        col.addWidget(self.bars_caption)
        self.bars = ProbBars()
        col.addWidget(self.bars)
        self.th_actual = label("", "muted", wrap=True)
        col.addWidget(self.th_actual)
        self.th_mode = label("", None, wrap=True)
        col.addWidget(self.th_mode)
        self.th_leader = label("", None, wrap=True)
        col.addWidget(self.th_leader)
        self.th_shift = label("", "muted", wrap=True)
        col.addWidget(self.th_shift)
        self.th_memory = label("", "hint", wrap=True)
        col.addWidget(self.th_memory)
        self.ranking_caption = label("", "muted", wrap=True)
        col.addWidget(self.ranking_caption)
        self.ranking = QListWidget()
        self.ranking.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.ranking.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.ranking.setMinimumHeight(130)
        self.ranking.setWordWrap(True)
        col.addWidget(self.ranking)
        col.addStretch(1)
        root.addWidget(side)

    def thought_widgets(self):
        return (self.th_title, self.bars_caption, self.bars, self.th_actual, self.th_mode, self.th_leader,
                self.th_shift, self.th_memory, self.ranking_caption, self.ranking)

    def retranslate(self):
        t = self.gw.t
        self.thoughts_box.setText(t("thoughts"))
        self.ranking_caption.setText(t("ranking"))
        self.peek_box.setText(t("peek"))
        self.peek_box.setToolTip(t("peek_tip"))
        self.new_button.setText(t("new_match"))
        self.end_button.setText(t("end_match"))
        self.menu_button.setText(t("menu"))
        self.review_title.setText(t("habits"))


# --- статистика ---


def match_outcome(m):
    """Итог матча для серий: выиграно раундов больше, чем у ИИ, - победа; поровну - ничья.
    Брошенный матч - поражение при любом счёте, как в статистике (правило 1.0.2)."""
    if m.get("abandoned"):
        return "loss"
    return "win" if m["wins"] > m["losses"] else ("loss" if m["wins"] < m["losses"] else "draw")


class StatsPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        body = page_widget()
        lay.addWidget(scroll_of(body))
        outer = QVBoxLayout(body)
        # страница не меньше своего содержимого: иначе в прокрутке карточки с постоянной
        # высотой (таблицы, графики) налезали друг на друга
        outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(12)
        top = QHBoxLayout()
        self.heading = label("", "heading")
        top.addWidget(self.heading)
        top.addStretch(1)
        self.menu_button = button("", None, lambda: gw.show_page("menu"))
        top.addWidget(self.menu_button)
        outer.addLayout(top)
        self.caption = label("", "section")
        outer.addWidget(self.caption)
        self.table = self._table()
        outer.addWidget(self.table)
        self.note = label("", "hint", wrap=True)
        outer.addWidget(self.note)
        self.chart_matches = LineChart()
        self.chart_matches.second_key = "bad"           # вторая линия - доля ИИ
        self.chart_streak = LineChart(percent=False)
        self.chart_streak.color_key, self.chart_streak.second_key = "accent", "warn"
        self.chart_streak.stepped = {0, 1}
        self.chart_streak.integer = True
        self.chart_levels = BarChart()
        self.chart_ai = BarChart()
        for c in self.charts():
            outer.addWidget(c)
        self.pp_caption = label("", "section", wrap=True)
        outer.addWidget(self.pp_caption)
        self.pp = self._table()
        outer.addWidget(self.pp)
        outer.addStretch(1)

    def charts(self):
        return (self.chart_matches, self.chart_streak, self.chart_levels, self.chart_ai)

    def refresh_charts(self):
        """Графики: доля выигранных раундов по матчам, по уровням и сила ИИ по паспорту."""
        t = self.gw.t
        g = self.gw
        for c in self.charts():
            c.set_theme(g.ctx.theme)
        cm = self.chart_matches
        cm.title, cm.empty_text, cm.x_label = t("chart_matches"), t("chart_matches_empty"), t("chart_match_x")
        cm.names = (t("series_you"), t("series_ai"))
        hist = g.match_history()
        cm.set_points([(i + 1, m["wins"] / m["rounds"]) for i, m in enumerate(hist)],
                      [(i + 1, m["losses"] / m["rounds"]) for i, m in enumerate(hist)])
        cs = self.chart_streak
        cs.title, cs.empty_text, cs.x_label = t("chart_streak"), t("chart_streak_empty"), t("chart_match_x")
        cs.names = (t("streak_now"), t("streak_record"))
        now, best = gamelog.streaks([{"n": i + 1, "outcome": match_outcome(m)} for i, m in enumerate(hist)])
        cs.set_points(now, best)
        cl = self.chart_levels
        cl.title, cl.empty_text = t("chart_levels"), t("chart_levels_empty")
        groups, you, ai = [], [], []
        totals = g.round_totals()
        for k in (3, 5):
            for lv in LEVELS:
                w, ti, lo = totals.get(f"{k}/{lv}", (0, 0, 0))
                n = w + ti + lo
                if not n:
                    continue
                groups.append(f"{k} · {t(lv)}")
                you.append(w / n)
                ai.append(lo / n)
        cl.set_data(groups, [(t("series_you"), "good", you), (t("series_ai"), "bad", ai)])
        ca = self.chart_ai
        ca.title, ca.empty_text = t("chart_ai_strength"), t("no_passport")
        pp = g.passport()
        bots = ("repeat", "cycle", "wsls", "markov2", "biased", "human", "random", "mirror", "exploit")
        if pp is None:
            ca.set_data([], [])
            return
        series = []
        for k, key, name in ((3, "accent", t("series_k3")), (5, "warn", t("series_k5"))):
            vals = []
            for b in bots:
                c = next((c for c in pp["checks"] if c["k"] == k and c["level"] == "strong" and c["bot"] == b), None)
                vals.append(c["after30"]["win"] if c else 0.0)
            series.append((name, key, vals))
        ca.set_data([t("b_" + b) for b in bots], series)

    @staticmethod
    def _table():
        tb = QTableWidget()
        tb.verticalHeader().setVisible(False)
        tb.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        tb.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        tb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        tb.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        return tb

    @staticmethod
    def _fill(tb, headers, rows):
        tb.clear()
        tb.setColumnCount(len(headers))
        tb.setHorizontalHeaderLabels(headers)
        tb.setRowCount(len(rows))
        for r, row in enumerate(rows):
            for c, v in enumerate(row):
                it = QTableWidgetItem(str(v))
                it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                tb.setItem(r, c, it)
        tb.setFixedHeight(tb.horizontalHeader().height() + 34 * max(1, len(rows)) + 6)
        for r in range(len(rows)):
            tb.setRowHeight(r, 34)

    def refresh(self):
        t = self.gw.t
        g = self.gw
        self.heading.setText(t("stats_title"))
        self.menu_button.setText(t("menu"))
        self.caption.setText(t("your_matches"))
        rounds = g.round_totals()
        rows = []
        for k in (3, 5):
            for lv in LEVELS:
                key = f"{k}/{lv}"
                e = g.ctx.stats.entry(key)
                rt = rounds.get(key, [0, 0, 0])
                if e["games"] or any(rt):
                    rows.append([f"{k} · {t(lv)}", e["games"], e["wins"], e["draws"], e["losses"],
                                 f"{rt[0]} / {rt[1]} / {rt[2]}"])
        self._fill(self.table, [t("col_setup"), t("col_matches"), t("col_wins"), t("col_draws"),
                                t("col_losses"), t("col_rounds")], rows)
        self.note.setText(t("stats_note"))
        self.refresh_charts()
        self.pp_caption.setText(t("passport"))
        pp = g.passport()
        if pp is None:
            self._fill(self.pp, [t("no_passport")], [])
            return
        bots = [b for b in ("repeat", "cycle", "wsls", "markov2", "biased", "human", "random", "mirror", "exploit")]
        head = [t("bot")] + [f"{k} · {t(lv)}" for k in (3, 5) for lv in LEVELS]
        rows = []
        for b in bots:
            row = [t("b_" + b)]
            for k in (3, 5):
                for lv in LEVELS:
                    c = next((c for c in pp["checks"] if c["k"] == k and c["level"] == lv and c["bot"] == b), None)
                    row.append(f"{pct(c['after30']['win'])}%" if c else "-")
            rows.append(row)
        self._fill(self.pp, head, rows)


# --- настройки ---


class SettingsPage(QWidget):
    def __init__(self, gw):
        super().__init__()
        self.gw = gw
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        body = page_widget()
        lay.addWidget(scroll_of(body))
        outer = QVBoxLayout(body)
        # страница не меньше своего содержимого: иначе в прокрутке карточки с постоянной
        # высотой (таблицы, графики) налезали друг на друга
        outer.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)
        outer.setContentsMargins(26, 22, 26, 22)
        outer.setSpacing(14)
        top = QHBoxLayout()
        self.heading = label("", "heading")
        top.addWidget(self.heading)
        top.addStretch(1)
        self.menu_button = button("", None, lambda: gw.show_page("menu"))
        top.addWidget(self.menu_button)
        outer.addLayout(top)
        box = card()
        box.setMaximumWidth(760)
        self.grid = QGridLayout(box)
        self.grid.setContentsMargins(22, 18, 22, 18)
        self.grid.setHorizontalSpacing(22)
        self.grid.setVerticalSpacing(16)
        self.grid.setColumnStretch(0, 1)
        self.rows = {}
        self.theme_combo = Combo()
        for k in theme.THEMES:
            self.theme_combo.addItem("", k)
        self.theme_combo.currentIndexChanged.connect(lambda i: gw.ctx.set_theme(self.theme_combo.itemData(i)))
        self._row("theme", self.theme_combo)
        self.lang_combo = Combo()
        self.lang_combo.addItem("Русский", "ru")
        self.lang_combo.addItem("English", "en")
        self.lang_combo.currentIndexChanged.connect(lambda i: gw.ctx.set_lang(self.lang_combo.itemData(i)))
        self._row("language", self.lang_combo)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(gw.ctx.sound.volume)
        self.volume.valueChanged.connect(gw.ctx.set_volume)
        self._row("volume", self.volume)
        self.delay = QSlider(Qt.Orientation.Horizontal)
        self.delay.setRange(0, 3000)
        self.delay.valueChanged.connect(lambda v: gw.change("delay_ms", int(v)))
        self._row("delay", self.delay)
        outer.addWidget(box)
        self.note = label("", "hint")
        outer.addWidget(self.note)
        outer.addStretch(1)

    def _row(self, key, widget):
        r = len(self.rows)
        names = QVBoxLayout()
        names.setSpacing(2)
        title = label("", "section")
        hint = label("", "hint", wrap=True)
        names.addWidget(title)
        names.addWidget(hint)
        self.grid.addLayout(names, r, 0)
        self.grid.addWidget(widget, r, 1)
        self.rows[key] = (title, hint)

    def retranslate(self):
        t = self.gw.t
        self.heading.setText(t("settings_title"))
        self.menu_button.setText(t("menu"))
        for key, (title, hint) in self.rows.items():
            title.setText(t(key))
            hint.setText(t(key + "_hint"))
        for i, k in enumerate(theme.THEMES):
            self.theme_combo.setItemText(i, t(k))
        self.note.setText(t("saved_note"))
        self.sync()

    def sync(self):
        g = self.gw
        for combo, value in ((self.theme_combo, g.ctx.theme), (self.lang_combo, g.ctx.lang)):
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)
        self.delay.blockSignals(True)
        self.delay.setValue(g.settings["delay_ms"])
        self.delay.blockSignals(False)


# --- сам виджет игры ---


class GameWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.t = translator(ctx.lang)
        self.settings = st.Settings(SCHEMA, ctx.file("settings.json"))
        self.session = None
        self.paused = False
        self.rng = random.Random()
        self._passport = None
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._demo_step)
        self.stack = QStackedWidget(self)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.stack)
        self.menu = MenuPage(self)
        self.play = PlayPage(self)
        self.stats = StatsPage(self)
        self.settings_page = SettingsPage(self)
        self.pages = {"menu": self.menu, "play": self.play, "stats": self.stats, "settings": self.settings_page}
        for p in self.pages.values():
            self.stack.addWidget(p)
        keys = [(str(i + 1), lambda i=i: self.on_sign(i)) for i in range(5)]
        keys += [("Escape", lambda: self.show_page("menu")), ("N", lambda: self.start_match()),
                 ("Space", self.toggle_pause)]
        for k, slot in keys:
            sc = QShortcut(QKeySequence(k), self)
            sc.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            sc.activated.connect(slot)
        ctx.changed.connect(self.on_ctx_changed)
        self.apply_theme()
        self.retranslate()
        self.show_page("menu")

    def minimumSizeHint(self):
        return QSize(980, 660)

    # --- общее ---

    def current_page(self):
        w = self.stack.currentWidget()
        return next(k for k, p in self.pages.items() if p is w)

    def show_page(self, name):
        if name != "play":
            self._abandon()                  # из меню в этот матч не вернуться
            self.timer.stop()
        self.stack.setCurrentWidget(self.pages[name])
        if name == "stats":
            self.stats.refresh()
        elif name == "settings":
            self.settings_page.sync()
        elif name == "menu":
            self.menu.sync(self.settings)
        elif name == "play" and self.session is not None:
            self._schedule()

    def change(self, key, value):
        if self.settings[key] == value:
            return
        self.settings.set(key, value)
        if key in ("k", "length", "level", "mode", "bot"):
            self.menu.sync(self.settings)
        elif key == "peek":
            s = self.session
            if value and s is not None and s.mode == "play" and not s.over:
                s.peeked = True
            self.refresh()
        elif key == "show_thoughts":
            self.refresh()

    def on_ctx_changed(self, what):
        if what == "theme":
            self.apply_theme()
        elif what == "lang":
            self.t = translator(self.ctx.lang)
            self.retranslate()

    def apply_theme(self):
        c = theme.palette(self.ctx.theme)
        for combo in self.findChildren(Combo):
            combo.set_arrow_color(c["text"])
        for chart in self.stats.charts():
            chart.set_theme(self.ctx.theme)
        self.refresh()
        self.update()

    def retranslate(self):
        self.menu.retranslate()
        self.play.retranslate()
        self.settings_page.retranslate()
        if self.current_page() == "stats":
            self.stats.refresh()
        self.refresh()

    def shutdown(self):
        """Окно закрывается: таймер показа стоп. Своих потоков у игры нет."""
        self._abandon()
        self.timer.stop()
        return True

    def passport(self):
        if self._passport is None:
            self._passport = load_json(PASSPORT)
        return self._passport

    def match_history(self):
        """Сыгранные в статистику матчи по порядку: [{k, level, rounds, wins, ties, losses}]."""
        data = load_json(self.ctx.file("matches.json"))
        if not isinstance(data, list):
            return []
        out = []
        for m in data:
            if (isinstance(m, dict) and m.get("k") in (3, 5) and m.get("level") in LEVELS
                    and all(isinstance(m.get(f), int) and not isinstance(m.get(f), bool) and m[f] >= 0
                            for f in ("rounds", "wins", "ties", "losses"))
                    and m["wins"] + m["ties"] + m["losses"] == m["rounds"] > 0):
                out.append(m)
        return out

    def round_totals(self):
        data = load_json(self.ctx.file("rounds.json"))
        if not isinstance(data, dict):
            return {}
        return {k: v for k, v in data.items()
                if isinstance(v, list) and len(v) == 3 and all(isinstance(x, int) and x >= 0 for x in v)}

    # --- матч ---

    def start_match(self, seed=None):
        self._abandon()
        s = self.settings
        if seed is None:
            seed = self.rng.randrange(2 ** 31)
        self.timer.stop()
        self.session = Session(s["k"], s["length"], s["level"], s["mode"], s["bot"], seed)
        self.session.peeked = s["peek"] and s["mode"] == "play"
        self.paused = False
        self.stack.setCurrentWidget(self.play)
        self.refresh()
        self._schedule()

    def on_sign(self, sign):
        s = self.session
        if s is None or s.over or s.mode != "play" or sign >= s.k or self.current_page() != "play":
            return
        rv = s.play(sign)
        self._after_round(rv)

    def _after_round(self, rv):
        self.ctx.sound.play({WIN: "capture", LOSS: "move"}.get(rv.result, "move"))
        if self.session.over:
            self._finish()
        self.refresh()
        self._schedule()

    def _schedule(self):
        s = self.session
        if s is None or s.mode != "demo" or s.over or self.paused or self.current_page() != "play":
            return
        self.timer.start(self.settings["delay_ms"])

    def _demo_step(self):
        s = self.session
        if s is None or s.mode != "demo" or s.over:
            return
        self._after_round(s.demo_step())

    def end_match(self):
        s = self.session
        if s is None or s.over:
            return
        self.timer.stop()
        s.end()
        self._finish()
        self.refresh()

    def toggle_pause(self):
        s = self.session
        if s is None or s.mode != "demo":
            return
        self.paused = not self.paused
        if self.paused:
            self.timer.stop()
        else:
            self._schedule()
        self.refresh()

    def _finish(self):
        s = self.session
        if s.recorded:
            return
        s.recorded = True
        outcome = s.outcome_for_human()
        if outcome and s.counts():
            self._record(outcome)
        if outcome:
            self.ctx.sound.play(outcome)

    def _abandon(self):
        """Матч бросили (новый матч, меню, закрытие окна): после первого раунда он идёт в
        статистику поражением, даже если вы вели. Без звука."""
        s = self.session
        if s is None or s.recorded:
            return
        outcome = s.abandon_outcome()
        if outcome is None:
            return
        s.recorded = True
        s.abandoned = True
        if not s.peeked:              # показ и матч без раундов отсеяны в abandon_outcome
            self._record(outcome)

    def _record(self, outcome):
        """Итог матча - в статистику, итоги раундов и журнал графиков."""
        s = self.session
        self.ctx.stats.record(s.stats_key(), outcome)
        totals = self.round_totals()
        sc = s.match.score()
        old = totals.get(s.stats_key(), [0, 0, 0])
        totals[s.stats_key()] = [old[0] + sc["wins"], old[1] + sc["ties"], old[2] + sc["losses"]]
        save_json(self.ctx.file("rounds.json"), totals)
        history = self.match_history()
        m = {"k": s.k, "level": s.level, "rounds": len(s.rounds), "wins": sc["wins"],
             "ties": sc["ties"], "losses": sc["losses"]}
        if s.abandoned:
            m["abandoned"] = True        # брошен: в статистике поражение при любом счёте
        history.append(m)
        save_json(self.ctx.file("matches.json"), history[-MAX_HISTORY:])

    # --- вид ---

    def sign_name(self, m):
        return self.t(NAMES[m])

    def refresh(self):
        s = self.session
        if s is None:
            return
        t = self.t
        pp = self.play
        th = self.ctx.theme
        demo = s.mode == "demo"
        m = s.match
        pp.heading.setText(f"{t('app_title')} · {s.k} · {t(s.level)}"
                           + (f" · {t('b_' + s.bot_key)}" if demo else ""))
        n = len(m.rounds)
        pp.round_label.setText(t("round_of", n=min(n + 1, m.length), total=m.length) if m.length
                               else t("round_inf", n=n if s.over else n + 1))
        sc = m.score()
        for lab, v in zip(pp.score_nums, (sc["wins"], sc["ties"], sc["losses"])):
            lab.setText(str(v))
        for lab, key in zip(pp.score_caps, ("bot_side" if demo else "you", "ties", "ai")):
            lab.setText(t(key))
        # статус
        if s.over:
            outcome = s.outcome_for_human()
            if outcome:
                restyle(pp.status, {"win": "statusWin", "loss": "statusLoss", "draw": "statusDraw"}[outcome])
                pp.status.setText(t(outcome))
            else:
                restyle(pp.status, "status")
                pp.status.setText(t("score_line", w=sc["wins"], t=sc["ties"], l=sc["losses"]))
            pp.commit.setText("")
        else:
            restyle(pp.status, "status")
            pp.status.setText(t("demo_wait", bot=t("b_" + s.bot_key)) if demo else t("pick", k=s.k))
            pp.commit.setText(t("committed", h=s.commit[:16] + "…" + s.commit[-6:]) if s.commit else "")
        pal = theme.palette(self.ctx.theme)
        pp.not_counted.setVisible(s.mode == "play" and s.peeked)
        pp.not_counted.setText(t("not_counted") if s.peeked else "")
        pp.not_counted.setStyleSheet(f"color: {pal['warn']}; font-weight: 600;")
        pp.forecast_note.setStyleSheet(f"color: {pal['warn']};")
        for i, b in enumerate(pp.sign_buttons):
            b.setVisible(i < s.k)
            b.setEnabled(not demo and not s.over)
            b.set_text(self.sign_name(i), th)
            b.mark = None
        rv = s.last_reveal()
        if rv is not None:
            res = {WIN: "r_win_bot" if demo else "r_win", LOSS: "r_loss"}.get(rv.result, "r_tie")
            pp.last.setText(t("last_round", you=t("bot_side") if demo else t("you"), h=self.sign_name(rv.human),
                              a=self.sign_name(rv.ai)) + "  →  " + t(res))
            pp.verify.setText(t("verified", a=self.sign_name(rv.ai), nonce=rv.nonce[:8]) if rv.verified(s.k)
                              else t("not_verified"))
            if rv.human == rv.ai:
                pp.sign_buttons[rv.human].mark = "both"
            else:
                pp.sign_buttons[rv.human].mark = "human"
                pp.sign_buttons[rv.ai].mark = "ai"
        else:
            pp.last.setText(t("first_round_bot") if demo else t("first_round"))
            pp.verify.setText("")
        for b in pp.sign_buttons:
            b.update()
        # разбор после матча
        pp.review.setVisible(s.over and bool(m.rounds))
        if s.over and m.rounds:
            habits = analyse(m.rounds, s.k)
            lines = [t("h_" + h["key"], rate=pct(h["rate"]), base=pct(h["base"]),
                       move=self.sign_name(h["move"]) if "move" in h else "") for h in habits[:5]]
            pp.review_text.setText("\n".join("• " + x for x in lines) if lines else t("habits_none"))
            at = caught_at(m.rounds)
            pp.review_caught.setText(t("caught", n=at) if at else t("not_caught"))
        even = (s.k - 1) / 2 / s.k
        pp.chart.set_data(m.human_share_curve(), m.ai_share_curve(), even,
                          (t("chart_title"), t("chart_bot") if demo else t("chart_you"), t("chart_ai"),
                           t("chart_even")), th)
        pp.end_button.setVisible(not s.over and m.length == 0)
        pp.pause_button.setVisible(demo and not s.over)
        pp.pause_button.setText(t("resume") if self.paused else t("pause"))
        self._refresh_thoughts()

    def peeking(self):
        """Сейчас виден ход ИИ до хода человека: флажок включён, матч против ИИ идёт."""
        s = self.session
        return (self.settings["peek"] and s is not None and s.mode == "play" and not s.over
                and s.match.pending is not None)

    def _thoughts_source(self):
        """(мысли, заголовок, подпись столбиков, сыгранный ход): до хода - только с
        подглядыванием, иначе - о прошлом раунде."""
        s = self.session
        t = self.t
        if self.peeking():
            return s.pending_thoughts(), t("thoughts_now"), t("predicted_now"), None
        rv = s.last_reveal()
        demo = s.mode == "demo"
        if rv is None:
            return None, t("thoughts_none_demo") if demo else t("thoughts_none"), "", None
        expected = t("expected_last_bot" if demo else "expected_last", n=rv.round_no + 1)
        return rv.thoughts, t("thoughts_round", n=rv.round_no + 1), expected, rv.human

    def _refresh_thoughts(self):
        s = self.session
        t = self.t
        pp = self.play
        show = self.settings["show_thoughts"]
        for w, v in ((pp.thoughts_box, show), (pp.peek_box, self.settings["peek"])):
            w.blockSignals(True)
            w.setChecked(v)
            w.blockSignals(False)
        pp.thoughts_hint.setVisible(show)
        # подсказка - о том, что сейчас на панели: в показе о боте, с подглядыванием - этот раунд
        pp.thoughts_hint.setText(t("thoughts_hint_demo") if s.mode == "demo" else
                                 t("thoughts_hint_now") if self.peeking() else t("thoughts_hint"))
        pp.peek_box.setVisible(s.mode == "play")
        peek = self.peeking()
        pp.ai_move_peek.setVisible(peek)
        pp.ai_move_peek.setText(t("ai_move_peek", move=self.sign_name(s.match.pending.move)) if peek else "")
        hidden = show and s.mode == "play" and not s.over and not peek
        pp.forecast_note.setVisible(hidden)
        pp.forecast_note.setText(t("forecast_hidden") if hidden else "")
        th, title, caption, actual = self._thoughts_source() if show else (None, "", "", None)
        for w in pp.thought_widgets():
            w.setVisible(show and th is not None)
        pp.th_title.setVisible(show)
        pp.th_title.setText(title)
        if not show or th is None:
            return
        pp.bars_caption.setText(caption)
        played = "bot_played" if s.mode == "demo" else "you_played"
        pp.th_actual.setText(t(played, move=self.sign_name(actual)) if actual is not None else "")
        pp.th_actual.setVisible(actual is not None)
        dist = th.get("dist") or [1 / s.k] * s.k
        target = max(range(s.k), key=lambda i: dist[i]) if th.get("mode") == "predict" else None
        pp.bars.set_data(dist, [self.sign_name(i) for i in range(s.k)], self.ctx.theme, target)
        mode = th.get("mode")
        if mode == "predict":
            pp.th_mode.setText(t("mode_predict", c=pct(th.get("confidence", 1.0))))
            lead = th.get("leader") or {}
            pp.th_leader.setText(t("leader", name=predictor_name(t, lead.get("key", ""), lead.get("params", {}))))
            j = th.get("shift", 0)
            pp.th_shift.setText(t("shift0") if j == 0 else t("shift1") if j == 1 else t("shiftn", n=j))
        elif mode == "guard":
            pp.th_mode.setText(t("mode_guard", n=th.get("guard_left", 0)))
            pp.th_leader.setText("")
            pp.th_shift.setText("")
        else:
            pp.th_mode.setText(t("mode_random"))
            pp.th_leader.setText("")
            pp.th_shift.setText("")
        for w in (pp.th_leader, pp.th_shift):
            w.setVisible(bool(w.text()))
        pp.th_memory.setText(t("memory", n=th["memory"]) if "memory" in th else "")
        pp.th_memory.setVisible("memory" in th)
        pp.ranking.clear()
        for r in th.get("ranking", []):
            shift = f" +{r['shift']}" if r["shift"] else ""
            pp.ranking.addItem(f"{r['score']:+.2f}   {predictor_name(t, r['key'], r['params'])}{shift}")
        pp.ranking.setVisible(bool(th.get("ranking")))
        pp.ranking_caption.setVisible(bool(th.get("ranking")))

