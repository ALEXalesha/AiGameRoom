"""Главная вкладка: карточки игр, поиск, тема, язык, громкость, общая статистика."""
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QFrame, QGridLayout, QHBoxLayout, QLineEdit, QScrollArea, QSlider,
                               QVBoxLayout, QWidget)

from aikit.stats import Stats
from aikit.widgets import button, label, segmented

CARD_W = 320
PREVIEW_W, PREVIEW_H = CARD_W - 28, (CARD_W - 28) * 9 // 16
SPACING = 16


class GameCard(QFrame):
    def __init__(self, home, entry):
        super().__init__()
        self.home = home
        self.entry = entry
        self.setObjectName("gameCard" if entry.ok else "gameCardBroken")
        self.setFixedWidth(CARD_W)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)
        self.preview = label(name="preview")
        self.preview.setFixedSize(PREVIEW_W, PREVIEW_H)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        path = entry.preview_path()
        if path:
            pm = QPixmap(path)
            if not pm.isNull():
                self.preview.setPixmap(pm.scaled(PREVIEW_W, PREVIEW_H, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                                                 Qt.TransformationMode.SmoothTransformation)
                                       .copy(0, 0, PREVIEW_W, PREVIEW_H))
        if self.preview.pixmap().isNull():
            self.preview.setText("?")
        lay.addWidget(self.preview)
        self.title = label(name="cardTitle")
        lay.addWidget(self.title)
        self.summary = label(name="muted", wrap=True)
        lay.addWidget(self.summary)
        self.note = label(name="hint", wrap=True)
        lay.addWidget(self.note)
        self.played = label(name="hint", wrap=True)
        lay.addWidget(self.played)
        self.error = label(name="error", wrap=True)
        self.error.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lay.addWidget(self.error)
        lay.addStretch(1)
        self.play = button("", "primary", lambda: home.window_.open_game(entry.id))
        self.play.setVisible(entry.ok)
        lay.addWidget(self.play)

    def retranslate(self, t, lang, opened, totals=None):
        e = self.entry
        if totals and totals["games"]:
            self.played.setText(t("played", g=totals["games"], w=totals["wins"], s=totals["best_streak"]))
        else:
            self.played.setText(t("not_played"))
        self.played.setVisible(e.ok)
        self.title.setText(e.title(lang))
        self.summary.setText(e.summary(lang))
        notes = []
        if e.info:
            notes.append(t("version", v=e.info["version"]))
            if not e.speaks(lang):
                notes.append(t("ru_only"))
        self.note.setText(" · ".join(notes))
        self.note.setVisible(bool(notes))
        open_error = getattr(e, "open_error", None)
        if e.error:
            self.error.setText(f"{t('broken')}: {e.error}")
        elif open_error:
            self.error.setText(t("open_failed", e=open_error))
        self.error.setVisible(bool(e.error or open_error))
        self.play.setText(t("opened") if opened else t("play"))

    def matches(self, query):
        if not query:
            return True
        e = self.entry
        hay = " ".join([e.folder] + [e.title(x) for x in ("ru", "en")] + [e.summary(x) for x in ("ru", "en")])
        return query.casefold() in hay.casefold()


class HomePage(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window_ = window
        self.setObjectName("page")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 18, 24, 12)
        lay.setSpacing(12)

        top = QHBoxLayout()
        top.setSpacing(12)
        self.heading = label(name="heading")
        top.addWidget(self.heading)
        top.addStretch(1)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.search.textChanged.connect(self.relayout)
        top.addWidget(self.search)
        lay.addLayout(top)

        bar = QHBoxLayout()
        bar.setSpacing(10)
        self.theme_label = label(name="muted")
        bar.addWidget(self.theme_label)
        box, self.theme_buttons = segmented({"dark": "", "light": ""}, window.set_theme)
        bar.addWidget(box)
        bar.addSpacing(14)
        self.lang_label = label(name="muted")
        bar.addWidget(self.lang_label)
        box, self.lang_buttons = segmented({"ru": "RU", "en": "EN"}, window.set_lang)
        bar.addWidget(box)
        bar.addSpacing(14)
        self.volume_label = label(name="muted")
        bar.addWidget(self.volume_label)
        self.volume = QSlider(Qt.Orientation.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setFixedWidth(160)
        self.volume.valueChanged.connect(window.set_volume)
        bar.addWidget(self.volume)
        bar.addStretch(1)
        self.count = label(name="hint")
        bar.addWidget(self.count)
        lay.addLayout(bar)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.inner = QWidget()
        self.inner.setObjectName("page")
        column = QVBoxLayout(self.inner)
        column.setContentsMargins(0, 4, 0, 4)
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        column.addLayout(self.grid)
        column.addStretch(1)            # карточки - своей высоты, не растягиваются на всю вкладку
        self.grid.setSpacing(SPACING)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self.scroll.setWidget(self.inner)
        lay.addWidget(self.scroll, 1)
        self.empty = label(name="muted")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self.empty)

        self.cards = []
        self.columns = 0
        self.set_entries(window.entries)

    def set_entries(self, entries):
        for c in self.cards:
            self.grid.removeWidget(c)
            c.deleteLater()
        self.cards = [GameCard(self, e) for e in entries]
        self.columns = 0
        self.retranslate()

    def totals(self):
        """Общая статистика: stats.json каждой игры в её папке данных (aikit.stats).
        Игра пишет его сама через ctx.stats - оболочке не нужно её открывать."""
        out = {}
        for c in self.cards:
            if c.entry.ok:
                out[c.entry.id] = Stats(os.path.join(self.window_.root, c.entry.id, "stats.json")).totals()
        return out

    def visible_cards(self):
        q = self.search.text().strip()
        return [c for c in self.cards if c.matches(q)]

    def relayout(self, *_):
        width = self.scroll.viewport().width() or self.width()
        cols = max(1, (width + SPACING) // (CARD_W + SPACING))
        shown = self.visible_cards()
        for c in self.cards:
            self.grid.removeWidget(c)
            c.setVisible(c in shown)
        for i, c in enumerate(shown):
            self.grid.addWidget(c, i // cols, i % cols)
        self.columns = cols
        t = self.window_.t
        self.empty.setText(t("no_games") if not self.cards else t("nothing_found"))
        self.empty.setVisible(not shown)

    def retranslate(self):
        w = self.window_
        t = w.t
        self.heading.setText(t("app"))
        self.search.setPlaceholderText(t("search"))
        self.theme_label.setText(t("theme"))
        self.theme_buttons["dark"].setText(t("theme_dark"))
        self.theme_buttons["light"].setText(t("theme_light"))
        self.lang_label.setText(t("lang"))
        self.volume_label.setText(t("volume"))
        totals = self.totals()
        played = sum(x["games"] for x in totals.values())
        self.count.setText(t("count", n=sum(c.entry.ok for c in self.cards))
                           + (" · " + t("played_total", n=played) if played else ""))
        for c in self.cards:
            c.retranslate(t, w.lang, w.is_open(c.entry.id), totals.get(c.entry.id))
        self.sync()
        self.relayout()

    def sync(self):
        """Переключатели - по общим настройкам (их могла поменять игра через ctx)."""
        w = self.window_
        self.theme_buttons[w.theme].setChecked(True)
        self.lang_buttons[w.lang].setChecked(True)
        self.volume.blockSignals(True)
        self.volume.setValue(w.volume)
        self.volume.blockSignals(False)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        width = self.scroll.viewport().width()
        if max(1, (width + SPACING) // (CARD_W + SPACING)) != self.columns:
            self.relayout()
