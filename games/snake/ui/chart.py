"""Простой график линии, нарисованный QPainter (без QtCharts): карточка с заголовком,
сеткой, подписями осей, линией с заливкой и последним значением."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from games.snake.ui import theme


def points_from(items, x_key, y_key):
    """Точки (x, y) из списка словарей паспорта; мусорные записи пропускаются."""
    out = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        x, y = item.get(x_key), item.get(y_key)
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
               for v in (x, y)):
            out.append((float(x), float(y)))
    return sorted(out)


def _fmt(v, percent):
    if percent:
        return f"{v * 100:.1f}%" if abs(v) < 10 else f"{v:.0f}%"
    if v != 0 and (abs(v) >= 1000 or abs(v) < 0.01):
        return f"{v:.2g}"
    return f"{v:.2f}" if abs(v) < 10 else f"{v:.0f}"


class Chart(QWidget):
    def __init__(self, title, color, x_label="", percent=False, log_y=False, parent=None):
        super().__init__(parent)
        self.title = title
        self.color = QColor(color)
        self.x_label = x_label
        self.percent = percent
        self.log_y = log_y
        self.points = []
        self.colors = theme.tokens("dark")
        self.setMinimumSize(300, 190)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(210)

    def set_points(self, points):
        self.points = list(points)
        self.setVisible(len(self.points) >= 2)
        self.update()

    def set_theme(self, name):
        self.colors = theme.tokens(name)
        self.update()

    def set_text(self, title, x_label):
        self.title, self.x_label = title, x_label
        self.update()

    def has_data(self):
        return len(self.points) >= 2

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        card = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(self.colors['line']), 1))
        p.setBrush(QColor(self.colors['card']))
        p.drawRoundedRect(card, 12, 12)

        title_font = QFont(self.font())
        title_font.setPointSizeF(10)
        title_font.setBold(True)
        small = QFont(self.font())
        small.setPointSizeF(8)
        p.setFont(title_font)
        p.setPen(QColor(self.colors['text']))
        p.drawText(QRectF(14, 8, self.width() - 28, 22), Qt.AlignmentFlag.AlignLeft |
                   Qt.AlignmentFlag.AlignVCenter, self.title)
        if not self.has_data():
            p.end()
            return

        xs = [x for x, _ in self.points]
        use_log = self.log_y and all(y > 0 for _, y in self.points)
        ys = [math.log10(y) if use_log else y for _, y in self.points]
        x0, x1 = xs[0], xs[-1]
        y0, y1 = min(ys), max(ys)
        if y1 - y0 < 1e-12:
            y0, y1 = y0 - 0.5, y1 + 0.5
        pad = (y1 - y0) * 0.08
        y0, y1 = y0 - pad, y1 + pad
        if x1 - x0 < 1e-12:
            x1 = x0 + 1

        # Последнее значение справа в заголовке.
        last = self.points[-1][1]
        p.setPen(self.color)
        p.drawText(QRectF(14, 8, self.width() - 28, 22), Qt.AlignmentFlag.AlignRight |
                   Qt.AlignmentFlag.AlignVCenter, _fmt(last, self.percent))

        plot = QRectF(58, 40, self.width() - 74, self.height() - 72)
        p.setFont(small)
        for i in range(5):
            t = i / 4
            yy = plot.bottom() - t * plot.height()
            p.setPen(QPen(QColor(self.colors['line']), 1))
            p.drawLine(QPointF(plot.left(), yy), QPointF(plot.right(), yy))
            value = y0 + t * (y1 - y0)
            value = 10 ** value if use_log else value
            p.setPen(QColor(self.colors['muted']))
            p.drawText(QRectF(4, yy - 8, plot.left() - 10, 16),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       _fmt(value, self.percent))
        p.setPen(QColor(self.colors['muted']))
        bottom = QRectF(plot.left(), plot.bottom() + 6, plot.width(), 16)
        p.drawText(bottom, Qt.AlignmentFlag.AlignLeft, f"{x0:g}")
        p.drawText(bottom, Qt.AlignmentFlag.AlignRight, f"{xs[-1]:g}")
        if self.x_label:
            p.drawText(bottom, Qt.AlignmentFlag.AlignHCenter, self.x_label)

        def at(x, y):
            return QPointF(plot.left() + (x - x0) / (x1 - x0) * plot.width(),
                           plot.bottom() - (y - y0) / (y1 - y0) * plot.height())

        line = QPainterPath(at(xs[0], ys[0]))
        for x, y in zip(xs[1:], ys[1:]):
            line.lineTo(at(x, y))
        fill = QPainterPath(line)
        fill.lineTo(at(xs[-1], y0))
        fill.lineTo(at(xs[0], y0))
        fill.closeSubpath()
        grad = QLinearGradient(plot.topLeft(), plot.bottomLeft())
        top = QColor(self.color)
        top.setAlpha(90)
        bottom_c = QColor(self.color)
        bottom_c.setAlpha(0)
        grad.setColorAt(0, top)
        grad.setColorAt(1, bottom_c)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawPath(fill)
        pen = QPen(self.color, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(line)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self.color)
        p.drawEllipse(at(xs[-1], ys[-1]), 3.5, 3.5)
        p.end()
