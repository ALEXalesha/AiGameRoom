"""Значок ИИ-Игротеки, нарисованный кодом: четыре плитки-игры - карта, крестик, нолик,
клетки доски. Тот же рисунок идёт в окно и в .ico сборки."""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap


def render(size=256):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 256
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#1f242e"))
    p.drawRoundedRect(QRectF(8 * s, 8 * s, 240 * s, 240 * s), 52 * s, 52 * s)
    tiles = [(28, 28, "#2f3540"), (132, 28, "#2f3540"), (28, 132, "#2f3540"), (132, 132, "#4a7ab8")]
    for x, y, color in tiles:
        p.setBrush(QColor(color))
        p.drawRoundedRect(QRectF(x * s, y * s, 96 * s, 96 * s), 20 * s, 20 * s)
    # карта
    p.setBrush(QColor("#f4f1ea"))
    p.drawRoundedRect(QRectF(52 * s, 42 * s, 48 * s, 68 * s), 7 * s, 7 * s)
    p.setBrush(QColor("#d8404f"))
    p.drawEllipse(QPointF(76 * s, 76 * s), 11 * s, 11 * s)
    # крестик
    pen = QPen(QColor("#5fb4ff"), 13 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(QPointF(156 * s, 52 * s), QPointF(204 * s, 100 * s))
    p.drawLine(QPointF(204 * s, 52 * s), QPointF(156 * s, 100 * s))
    # нолик
    p.setPen(QPen(QColor("#ff8a9a"), 13 * s))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QPointF(76 * s, 180 * s), 25 * s, 25 * s)
    # клетки доски
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#e6e8ec"))
    for i in range(3):
        for j in range(3):
            if (i + j) % 2 == 0:
                p.drawRect(QRectF((150 + i * 20) * s, (150 + j * 20) * s, 20 * s, 20 * s))
    p.end()
    return img


def app_icon():
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render(size)))
    return icon
