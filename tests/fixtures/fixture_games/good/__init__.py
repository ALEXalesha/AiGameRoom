"""Исправная игра без pause/resume: оболочка сама гасит её таймеры."""
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from aikit.charts import GameCharts  # noqa: F401  графики статистики по контракту

GAME_INFO = {
    "id": "good",
    "title": {"ru": "Хорошая", "en": "Good"},
    "summary": {"ru": "образец без пауз", "en": "sample without pause hooks"},
    "preview": "preview.png",
    "version": "1.0.0",
}


class Widget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        self.ticks = 0
        self.seen = []
        self.timer = QTimer(self)
        self.timer.setInterval(5)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.shutdowns = 0
        lay = QVBoxLayout(self)
        lay.addWidget(QLabel("good"))
        ctx.changed.connect(self.seen.append)

    def tick(self):
        self.ticks += 1

    def shutdown(self):
        self.shutdowns += 1
        self.timer.stop()
        return True


def create_widget(ctx):
    return Widget(ctx)
