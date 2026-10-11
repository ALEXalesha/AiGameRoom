"""Знаки, нарисованные своим кодом (QPainter): камень, бумага, ножницы, Спок, ящерица.
Без картинок и без эмодзи - шрифт эмодзи есть не везде, а кадры offscreen рисуют его
квадратиками."""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPen, QPixmap

COLORS = {
    "dark": ["#b9a58a", "#7fb4ff", "#ff7a7a", "#6fd3a8", "#e8b04a"],
    "light": ["#8a6f4c", "#2f6fd0", "#d8404f", "#16946e", "#b07a10"],
}


def color(sign, theme="dark"):
    return QColor(COLORS.get(theme, COLORS["dark"])[sign])


def _rock(p, r, c):
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    pts = [(-0.78, 0.18), (-0.55, -0.42), (-0.05, -0.62), (0.5, -0.45), (0.8, 0.0),
           (0.62, 0.48), (0.05, 0.62), (-0.55, 0.52)]
    path = QPainterPath()
    path.moveTo(cx + pts[0][0] * s, cy + pts[0][1] * s)
    for x, y in pts[1:]:
        path.lineTo(cx + x * s, cy + y * s)
    path.closeSubpath()
    p.setBrush(c)
    p.setPen(QPen(c.darker(150), max(1.0, s * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(c.lighter(130), max(1.0, s * 0.05), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.drawLine(QPointF(cx - 0.35 * s, cy - 0.3 * s), QPointF(cx + 0.05 * s, cy - 0.42 * s))


def _paper(p, r, c):
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    p.save()
    p.translate(cx, cy)
    p.rotate(-8)
    w, h = 1.05 * s, 1.35 * s
    fold = 0.3 * s
    path = QPainterPath()
    path.moveTo(-w / 2, -h / 2)
    path.lineTo(w / 2 - fold, -h / 2)
    path.lineTo(w / 2, -h / 2 + fold)
    path.lineTo(w / 2, h / 2)
    path.lineTo(-w / 2, h / 2)
    path.closeSubpath()
    p.setBrush(c)
    p.setPen(QPen(c.darker(150), max(1.0, s * 0.05), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                  Qt.PenJoinStyle.RoundJoin))
    p.drawPath(path)
    p.setPen(QPen(c.darker(170), max(1.0, s * 0.06), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    for i in range(3):
        y = -h / 2 + h * (0.35 + 0.18 * i)
        p.drawLine(QPointF(-w / 2 + 0.18 * s, y), QPointF(w / 2 - 0.18 * s, y))
    p.restore()


def _scissors(p, r, c):
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    pen = QPen(c, max(1.5, s * 0.16), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawLine(QPointF(cx - 0.3 * s, cy + 0.2 * s), QPointF(cx + 0.45 * s, cy - 0.75 * s))
    p.drawLine(QPointF(cx + 0.3 * s, cy + 0.2 * s), QPointF(cx - 0.45 * s, cy - 0.75 * s))
    p.setPen(QPen(c, max(1.5, s * 0.12)))
    for dx in (-0.38, 0.38):
        p.drawEllipse(QPointF(cx + dx * s, cy + 0.48 * s), 0.25 * s, 0.25 * s)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(c.darker(140))
    p.drawEllipse(QPointF(cx, cy - 0.1 * s), 0.08 * s, 0.08 * s)


def _spock(p, r, c):
    """Ладонь с пальцами, разведёнными по два: приветствие вулканца."""
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    p.setPen(QPen(c.darker(150), max(1.0, s * 0.05)))
    p.setBrush(c)
    p.drawRoundedRect(QRectF(cx - 0.42 * s, cy - 0.05 * s, 0.84 * s, 0.7 * s), 0.2 * s, 0.2 * s)
    fw = 0.17 * s
    for x, tilt in ((-0.4, -9), (-0.2, -9), (0.06, 9), (0.26, 9)):
        p.save()
        p.translate(cx + (x + 0.085) * s, cy + 0.05 * s)
        p.rotate(tilt)
        p.drawRoundedRect(QRectF(-fw / 2, -0.72 * s, fw, 0.8 * s), fw / 2, fw / 2)
        p.restore()
    p.save()
    p.translate(cx - 0.42 * s, cy + 0.32 * s)
    p.rotate(-50)
    p.drawRoundedRect(QRectF(-fw / 2, -0.5 * s, fw, 0.55 * s), fw / 2, fw / 2)
    p.restore()


def _lizard(p, r, c):
    cx, cy, s = r.center().x(), r.center().y(), min(r.width(), r.height()) / 2
    p.save()
    p.translate(cx, cy)
    p.rotate(-35)
    legs = QPen(c, max(1.2, s * 0.1), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(legs)
    for y in (-0.22, 0.25):
        p.drawLine(QPointF(-0.1 * s, y * s), QPointF(-0.38 * s, (y - 0.12) * s))
        p.drawLine(QPointF(0.1 * s, y * s), QPointF(0.38 * s, (y - 0.12) * s))
    tail = QPainterPath()
    tail.moveTo(0, 0.4 * s)
    tail.cubicTo(QPointF(0.1 * s, 0.7 * s), QPointF(-0.3 * s, 0.8 * s), QPointF(-0.15 * s, 0.98 * s))
    p.setPen(QPen(c, max(1.2, s * 0.12), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(tail)
    p.setPen(QPen(c.darker(150), max(1.0, s * 0.04)))
    p.setBrush(c)
    p.drawEllipse(QRectF(-0.17 * s, -0.4 * s, 0.34 * s, 0.85 * s))
    p.drawEllipse(QPointF(0, -0.58 * s), 0.17 * s, 0.2 * s)
    p.restore()


DRAW = (_rock, _paper, _scissors, _spock, _lizard)


def draw_sign(p, sign, rect, theme="dark", col=None):
    p.save()
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    DRAW[sign](p, QRectF(rect), QColor(col) if col is not None else color(sign, theme))
    p.restore()


def render(sign, size=64, theme="dark"):
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    draw_sign(p, sign, QRectF(size * 0.08, size * 0.08, size * 0.84, size * 0.84), theme)
    p.end()
    return img


def render_icon(size=256):
    """Иконка программы: камень, бумага и ножницы по кругу на тёмном фоне."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#272c36"))
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.2, size * 0.2)
    for i in range(3):
        ang = -math.pi / 2 + i * 2 * math.pi / 3
        x = size / 2 + math.cos(ang) * size * 0.25
        y = size / 2 + math.sin(ang) * size * 0.25 + size * 0.03
        g = size * 0.42
        draw_sign(p, i, QRectF(x - g / 2, y - g / 2, g, g), "dark")
    p.end()
    return img


def app_icon():
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(QPixmap.fromImage(render_icon(s)))
    return icon
