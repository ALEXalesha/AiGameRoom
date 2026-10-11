"""Виджеты, нарисованные своим кодом: кнопка-знак, график доли побед, столбики прогноза."""
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from aikit import theme as aitheme
from games.rockpaper.ui import glyphs


def _font(px, bold=False):
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    f.setBold(bold)
    return f


class SignButton(QWidget):
    """Большая кнопка со знаком, подписью и клавишей."""
    clicked = Signal(int)

    def __init__(self, sign, parent=None):
        super().__init__(parent)
        self.sign = sign
        self.text = ""
        self.key = str(sign + 1)
        self.theme = "dark"
        self.hover = False
        self.mark = None          # None, 'human', 'ai', 'both' - подсветка после раунда
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self.setMinimumSize(96, 120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self):
        return QSize(130, 132)

    def set_text(self, text, theme):
        self.text = text
        self.theme = theme
        self.update()

    def enterEvent(self, e):
        self.hover = True
        self.update()

    def leaveEvent(self, e):
        self.hover = False
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton and self.isEnabled() and self.rect().contains(e.position().toPoint()):
            self.clicked.emit(self.sign)

    def paintEvent(self, e):
        pal = aitheme.palette(self.theme)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        border = QColor(pal["accent"] if self.hover and self.isEnabled() else pal["border"])
        if self.mark == "human":
            border = QColor(pal["good"])
        elif self.mark == "ai":
            border = QColor(pal["bad"])
        elif self.mark == "both":
            border = QColor(pal["warn"])
        p.setPen(QPen(border, 2 if self.mark or self.hover else 1))
        p.setBrush(QColor(pal["surface2"] if self.isEnabled() else pal["surface"]))
        p.drawRoundedRect(r, 14, 14)
        g = min(r.width() - 20, r.height() - 46)
        glyphs.draw_sign(p, self.sign, QRectF(r.center().x() - g / 2, r.top() + 8, g, g), self.theme)
        p.setPen(QColor(pal["text"] if self.isEnabled() else pal["muted"]))
        p.setFont(_font(14, True))
        p.drawText(QRectF(r.left(), r.bottom() - 36, r.width(), 20), Qt.AlignmentFlag.AlignCenter, self.text)
        p.setPen(QColor(pal["muted"]))
        p.setFont(_font(11))
        p.drawText(QRectF(r.left(), r.bottom() - 18, r.width(), 14), Qt.AlignmentFlag.AlignCenter, self.key)
        p.end()


class ShareChart(QWidget):
    """Доля выигранных раундов по ходу матча: ваша и ИИ, линия «поровну»."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = "dark"
        self.human = []
        self.ai = []
        self.even = 1 / 3
        self.labels = ("", "", "", "")
        self.setMinimumHeight(140)

    def set_data(self, human, ai, even, labels, theme):
        self.human, self.ai, self.even, self.labels, self.theme = list(human), list(ai), even, labels, theme
        self.update()

    def sizeHint(self):
        return QSize(500, 220)

    def paintEvent(self, e):
        pal = aitheme.palette(self.theme)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        title, you, ai, even = self.labels
        p.setFont(_font(13, True))
        p.setPen(QColor(pal["text"]))
        p.drawText(QRectF(0, 0, self.width(), 20), Qt.AlignmentFlag.AlignLeft, title)
        plot = QRectF(36, 28, max(10, self.width() - 46), max(10, self.height() - 52))
        p.setFont(_font(11))
        for v in (0, 0.25, 0.5, 0.75, 1.0):
            y = plot.bottom() - v * plot.height()
            p.setPen(QPen(QColor(pal["grid"]), 1))
            p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            p.setPen(QColor(pal["muted"]))
            p.drawText(QRectF(0, y - 8, 32, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{round(v * 100)}%")
        y = plot.bottom() - self.even * plot.height()
        p.setPen(QPen(QColor(pal["muted"]), 1, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
        n = max(len(self.human), 1)
        for series, col in ((self.human, pal["good"]), (self.ai, pal["bad"])):
            if not series:
                continue
            path = QPainterPath()
            for i, v in enumerate(series):
                x = plot.left() + (i + 1) / n * plot.width() if n > 1 else plot.left()
                pt = QPointF(x, plot.bottom() - v * plot.height())
                if i == 0:
                    path.moveTo(pt)
                else:
                    path.lineTo(pt)
            p.setPen(QPen(QColor(col), 2.2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawPath(path)
        # подписи
        ly = self.height() - 18
        x = plot.left()
        for text, col, dash in ((you, pal["good"], False), (ai, pal["bad"], False), (even, pal["muted"], True)):
            p.setPen(QPen(QColor(col), 2.2, Qt.PenStyle.DashLine if dash else Qt.PenStyle.SolidLine))
            p.drawLine(QPointF(x, ly + 8), QPointF(x + 18, ly + 8))
            p.setPen(QColor(pal["muted"]))
            p.drawText(QRectF(x + 22, ly, 120, 16), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)
            x += 30 + p.fontMetrics().horizontalAdvance(text) + 18
        p.setPen(QColor(pal["muted"]))
        p.drawText(QRectF(plot.right() - 80, ly, 80, 16), Qt.AlignmentFlag.AlignRight, str(len(self.human)))
        p.end()


class ProbBars(QWidget):
    """Столбики: вероятность каждого вашего хода по мнению ИИ."""
    ROW = 30

    def __init__(self, parent=None):
        super().__init__(parent)
        self.theme = "dark"
        self.dist = []
        self.names = []
        self.target = None          # ход, который ИИ ждёт

    def set_data(self, dist, names, theme, target=None):
        self.dist, self.names, self.theme, self.target = list(dist), list(names), theme, target
        self.updateGeometry()
        self.update()

    def sizeHint(self):
        return QSize(280, max(1, len(self.dist)) * self.ROW)

    def minimumSizeHint(self):
        return self.sizeHint()

    def paintEvent(self, e):
        pal = aitheme.palette(self.theme)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setFont(_font(12))
        w = self.width()
        for i, v in enumerate(self.dist):
            y = i * self.ROW
            glyphs.draw_sign(p, i, QRectF(0, y + 3, self.ROW - 6, self.ROW - 6), self.theme)
            name = self.names[i] if i < len(self.names) else ""
            p.setPen(QColor(pal["text"]))
            p.drawText(QRectF(self.ROW, y, 80, self.ROW), Qt.AlignmentFlag.AlignVCenter, name)
            bx = self.ROW + 84
            bw = max(10, w - bx - 46)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal["surface2"]))
            p.drawRoundedRect(QRectF(bx, y + 9, bw, self.ROW - 18), 4, 4)
            p.setBrush(QColor(pal["warn"] if i == self.target else pal["accent"]))
            p.drawRoundedRect(QRectF(bx, y + 9, bw * max(0.0, min(1.0, v)), self.ROW - 18), 4, 4)
            p.setPen(QColor(pal["text"]))
            p.drawText(QRectF(w - 44, y, 44, self.ROW), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{round(v * 100)}%")
        p.end()
