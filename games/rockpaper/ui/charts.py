"""Графики статистики на QPainter (без QtCharts): линия и столбики.

Линия - по образцу AiCar/chart.py (а там - нейро-змейки): карточка с заголовком, сеткой,
делениями и подписями осей, линия с заливкой, последнее значение в углу; вторая линия
приглушённая, тогда в углу оба значения с подписями - они же легенда. Пока точек меньше
двух, карточка говорит словами, откуда возьмётся график.

Столбики - группы по одной на уровень или бота, в группе столбик на каждую серию, доли
от 0 до 100 %. Цвета берутся из темы aikit, поэтому графики меняются вместе с темой.

Модуль сделан для RockPaperAi и потом переедет в aikit (правило Алексея 10.10: графики
статистики во всех играх с ИИ).
"""
import math

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from aikit import theme as aitheme

LEFT, TOP, RIGHT, BOTTOM = 52, 42, 16, 44


def clean(points):
    """Только конечные пары чисел, по возрастанию x: мусор из файла не рисуется."""
    out = []
    for item in points if isinstance(points, (list, tuple)) else []:
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            continue
        x, y = item
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (x, y)):
            out.append((float(x), float(y)))
    return sorted(out)


def x_ticks(x0, x1, most=6):
    """Целые деления оси x шагом 1, 2, 5, 10, 20, 50...: не больше most штук."""
    span = max(x1 - x0, 1e-9)
    k = 0
    while True:
        step = (1, 2, 5)[k % 3] * 10 ** (k // 3)
        if span / step <= most - 1:
            break
        k += 1
    t = math.ceil(x0 / step) * step
    out = []
    while t <= x1 + 1e-9:
        out.append(t)
        t += step
    return out or [x0]


def pct(v):
    return f"{v * 100:.0f}%"


class _Card(QWidget):
    HEIGHT = 230

    def __init__(self, title="", empty_text="", parent=None):
        super().__init__(parent)
        self.title = title
        self.empty_text = empty_text
        self.theme = "dark"
        self.setMinimumSize(300, self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(self.HEIGHT)

    def sizeHint(self):
        return QSize(560, self.HEIGHT)

    def set_theme(self, name):
        self.theme = name
        self.update()

    def pal(self):
        return aitheme.palette(self.theme)

    def fonts(self):
        title = QFont("Segoe UI")
        title.setPixelSize(14)
        title.setBold(True)
        small = QFont("Segoe UI")
        small.setPixelSize(11)
        return title, small

    def frame(self, p, corner=()):
        """Карточка, заголовок слева и подписи справа (текст, цвет)."""
        pal = self.pal()
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(pal["border"]), 1))
        p.setBrush(QColor(pal["surface"]))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 12, 12)
        title_font, small = self.fonts()
        head = QRectF(14, 8, self.width() - 28, 22)
        p.setFont(title_font)
        right = head.right()
        for text, colour in reversed(list(corner)):
            w = p.fontMetrics().horizontalAdvance(text)
            p.setPen(QColor(colour))
            p.drawText(QRectF(right - w, head.top(), w + 1, head.height()),
                       Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            right -= w
        p.setPen(QColor(pal["text"]))
        title = p.fontMetrics().elidedText(self.title, Qt.TextElideMode.ElideRight,
                                           int(max(40, right - head.left() - 12)))
        p.drawText(head, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, title)
        return small

    def empty(self, p):
        pal = self.pal()
        f = QFont("Segoe UI")
        f.setPixelSize(13)
        p.setFont(f)
        p.setPen(QColor(pal["muted"]))
        p.drawText(QRectF(24, 40, self.width() - 48, self.height() - 56),
                   Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.empty_text)

    def grid(self, p, plot, small):
        """Сетка по y от 0 до 100 % через 25 %."""
        pal = self.pal()
        p.setFont(small)
        for v in (0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - v * plot.height()
            p.setPen(QPen(QColor(pal["grid"]), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(pal["muted"]))
            p.drawText(QRectF(2, y - 8, plot.left() - 8, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, pct(v))


class LineChart(_Card):
    """Доли (0..1) по номеру: первая линия - главная, вторая - приглушённая."""

    def __init__(self, title="", empty_text="", x_label="", names=("", ""), parent=None):
        super().__init__(title, empty_text, parent)
        self.x_label = x_label
        self.names = names
        self.points = []
        self.second = []
        self.color_key = "good"

    def set_points(self, points, second=None):
        self.points = clean(points)
        self.second = clean(second or [])
        self.update()

    def has_data(self):
        return len(self.points) >= 2

    def paintEvent(self, event):
        pal = self.pal()
        p = QPainter(self)
        corner = []
        if self.points:
            corner = [(f"{self.names[0]} ", pal["muted"]), (pct(self.points[-1][1]), pal[self.color_key])]
            if self.second:
                corner += [(f"   {self.names[1]} ", pal["muted"]), (pct(self.second[-1][1]), pal["bad"])]
        small = self.frame(p, corner)
        if not self.has_data():
            self.empty(p)
            p.end()
            return
        plot = QRectF(LEFT, TOP, self.width() - LEFT - RIGHT, self.height() - TOP - BOTTOM)
        self.grid(p, plot, small)
        xs = [x for s in (self.points, self.second) for x, _ in s]
        x0, x1 = min(xs), max(xs)
        if x1 - x0 < 1e-12:
            x1 = x0 + 1

        def at(x, y):
            return QPointF(plot.left() + (x - x0) / (x1 - x0) * plot.width(),
                           plot.bottom() - max(0.0, min(1.0, y)) * plot.height())

        p.setPen(QPen(QColor(pal["muted"]), 1))
        for t in x_ticks(x0, x1, most=int(max(4, min(10, plot.width() // 70)))):
            x = at(t, 0).x()
            p.drawLine(QPointF(x, plot.bottom()), QPointF(x, plot.bottom() + 4))
            p.drawText(QRectF(x - 30, plot.bottom() + 5, 60, 14), Qt.AlignmentFlag.AlignHCenter, f"{t:g}")
        if self.x_label:
            p.drawText(QRectF(plot.left(), plot.bottom() + 22, plot.width(), 16),
                       Qt.AlignmentFlag.AlignHCenter, self.x_label)

        def path(points):
            line = QPainterPath(at(*points[0]))
            for x, y in points[1:]:
                line.lineTo(at(x, y))
            return line

        if len(self.second) >= 2:
            p.setPen(QPen(QColor(pal["bad"]), 1.6))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path(self.second))
        colour = QColor(pal[self.color_key])
        line = path(self.points)
        fill = QPainterPath(line)
        fill.lineTo(at(self.points[-1][0], 0))
        fill.lineTo(at(self.points[0][0], 0))
        fill.closeSubpath()
        grad = QLinearGradient(plot.topLeft(), plot.bottomLeft())
        top = QColor(colour)
        top.setAlpha(90)
        bottom = QColor(colour)
        bottom.setAlpha(0)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(fill)
        p.setPen(QPen(colour, 2.2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(colour)
        p.drawEllipse(at(*self.points[-1]), 3.5, 3.5)
        p.end()


class BarChart(_Card):
    """Группы столбиков: groups - подписи групп, series - [(подпись, ключ цвета темы, [доли])]."""

    def __init__(self, title="", empty_text="", parent=None):
        super().__init__(title, empty_text, parent)
        self.groups = []
        self.series = []

    def set_data(self, groups, series):
        self.groups = list(groups)
        self.series = [(name, key, [max(0.0, min(1.0, float(v))) for v in values]) for name, key, values in series]
        self.update()

    def has_data(self):
        return bool(self.groups) and bool(self.series)

    def paintEvent(self, event):
        pal = self.pal()
        p = QPainter(self)
        corner = []
        for i, (name, key, _) in enumerate(self.series):
            corner += [("■ ", pal[key]), (name + ("   " if i < len(self.series) - 1 else ""), pal["muted"])]
        small = self.frame(p, corner if self.has_data() else ())
        if not self.has_data():
            self.empty(p)
            p.end()
            return
        plot = QRectF(LEFT, TOP, self.width() - LEFT - RIGHT, self.height() - TOP - BOTTOM)
        self.grid(p, plot, small)
        n, m = len(self.groups), len(self.series)
        slot = plot.width() / n
        bar = min(34.0, slot * 0.8 / m)
        for gi, label in enumerate(self.groups):
            cx = plot.left() + slot * (gi + 0.5)
            x = cx - bar * m / 2
            for name, key, values in self.series:
                v = values[gi] if gi < len(values) else 0.0
                h = v * plot.height()
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(QColor(pal[key]))
                p.drawRoundedRect(QRectF(x + 1, plot.bottom() - h, bar - 2, h), 3, 3)
                if bar >= 22:
                    p.setPen(QColor(pal["text"]))
                    p.drawText(QRectF(x - 6, plot.bottom() - h - 15, bar + 12, 14), Qt.AlignmentFlag.AlignHCenter,
                               pct(v))
                x += bar
            p.setPen(QColor(pal["muted"]))
            text = p.fontMetrics().elidedText(label, Qt.TextElideMode.ElideRight, int(slot - 4))
            p.drawText(QRectF(cx - slot / 2, plot.bottom() + 6, slot, 30),
                       Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, text)
        p.end()
