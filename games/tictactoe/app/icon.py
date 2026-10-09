"""Иконка рисуется кодом: тёмная плитка, поле 3x3, крестики по диагонали и золотая линия."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap

from games.tictactoe.app import theme


def render(size=256):
    p_ = theme.palette("dark")
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = float(size)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(p_["surface"]))
    p.drawRoundedRect(QRectF(0, 0, s, s), s * 0.2, s * 0.2)

    pad, gap = s * 0.1, s * 0.035
    cell = (s - 2 * pad - 2 * gap) / 3
    marks = {(0, 0): 1, (1, 1): 1, (2, 2): 1, (0, 2): -1, (2, 0): -1}
    for r in range(3):
        for c in range(3):
            rect = QRectF(pad + c * (cell + gap), pad + r * (cell + gap), cell, cell)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(p_["tile"]))
            p.drawRoundedRect(rect, cell * 0.16, cell * 0.16)
            v = marks.get((r, c))
            if v is None:
                continue
            inner = rect.adjusted(cell * 0.25, cell * 0.25, -cell * 0.25, -cell * 0.25)
            pen = QPen(QColor(p_["x" if v == 1 else "o"]), max(1.5, cell * 0.14))
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            if v == 1:
                p.drawLine(inner.topLeft(), inner.bottomRight())
                p.drawLine(inner.topRight(), inner.bottomLeft())
            else:
                p.drawEllipse(inner)
    pen = QPen(QColor(p_["win"]), max(2.0, s * 0.05))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    a = pad + cell * 0.2
    b = s - pad - cell * 0.2
    p.drawLine(QPointF(a, a), QPointF(b, b))
    p.end()
    return image


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon
