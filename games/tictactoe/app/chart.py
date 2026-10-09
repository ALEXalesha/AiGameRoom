"""Кривая обучения из паспорта: доля побед против случайного и против бота по числу партий."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from games.tictactoe.app import theme


def games_label(g):
    if g >= 1000:
        return f"{g / 1000:g} тыс."
    return str(g)


class CurveChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.curve = []
        self.marks = []          # [(партий, подпись)] - где сняты уровни
        self.colors = theme.palette("dark")
        self.setMinimumHeight(260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_data(self, curve, marks=()):
        self.curve = list(curve)
        self.marks = list(marks)
        self.update()

    def set_theme(self, name):
        self.colors = theme.palette(name)
        self.update()

    def series(self):
        return [("против случайного", "vs_random", self.colors["x"]),
                ("против бота «выиграй или помешай»", "vs_bot", self.colors["o"])]

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self.colors
        small = QFont(self.font())
        small.setPixelSize(12)
        p.setFont(small)
        plot = QRectF(46, 34, self.width() - 64, self.height() - 78)

        # легенда
        x = plot.left()
        for name, _, color in self.series():
            p.setPen(QPen(QColor(color), 3))
            p.drawLine(QPointF(x, 16), QPointF(x + 18, 16))
            p.setPen(QColor(col["muted"]))
            p.drawText(QPointF(x + 24, 20), name)
            x += 24 + p.fontMetrics().horizontalAdvance(name) + 26

        # сетка
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(QColor(col["grid"]), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(col["muted"]))
            p.drawText(QRectF(0, y - 8, plot.left() - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, f"{i * 25}%")
        if not self.curve:
            p.setPen(QColor(col["muted"]))
            p.drawText(plot, Qt.AlignmentFlag.AlignCenter, "нет данных")
            p.end()
            return

        last = max(pt["games"] for pt in self.curve)

        def at(games, rate):
            return QPointF(plot.left() + plot.width() * games / last, plot.bottom() - plot.height() * rate)

        # где сняты уровни
        dash = QPen(QColor(col["muted"]), 1, Qt.PenStyle.DashLine)
        for games, label in self.marks:
            if 0 < games <= last:
                pt = at(games, 1.0)
                p.setPen(dash)
                p.drawLine(pt, QPointF(pt.x(), plot.bottom()))
                p.setPen(QColor(col["muted"]))
                p.drawText(QPointF(pt.x() + 4, plot.bottom() - 6), label)

        # подписи по оси партий
        p.setPen(QColor(col["muted"]))
        for i in range(5):
            g = last * i / 4
            pt = at(g, 0)
            p.drawText(QRectF(pt.x() - 40, plot.bottom() + 6, 80, 16), Qt.AlignmentFlag.AlignCenter,
                       games_label(round(g)))
        p.drawText(QRectF(plot.left(), plot.bottom() + 24, plot.width(), 18), Qt.AlignmentFlag.AlignCenter,
                   "партий самоигры")

        for _, keyname, color in self.series():
            path = QPainterPath()
            pts = [at(0, 0)] + [at(pt["games"], pt[keyname]) for pt in self.curve]
            path.moveTo(pts[1])
            for pt in pts[2:]:
                path.lineTo(pt)
            pen = QPen(QColor(color), 2.5)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        p.end()
