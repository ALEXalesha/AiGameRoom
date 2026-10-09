"""Поле, нарисованное QPainter: плитки, крестики и нолики, выигрышная линия, мысли сети."""
import math

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from games.tictactoe.app import theme


def mix(a, b, t):
    """Цвет между a и b, t от 0 до 1."""
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class BoardWidget(QWidget):
    cellClicked = Signal(int, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.board = np.zeros((3, 3), np.int8)
        self.line = None
        self.last = None
        self.thoughts = None
        self.interactive = True
        self.hints = True
        self.hover = None
        self.colors = theme.palette("dark")
        self.setMouseTracking(True)
        self.setMinimumSize(260, 260)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # --- состояние ---

    def set_state(self, board, line=None, last=None, thoughts=None, interactive=True):
        self.board = np.array(board)
        self.line = line
        self.last = last
        self.thoughts = thoughts
        self.interactive = interactive
        if not interactive:
            self.hover = None
        self.setCursor(Qt.CursorShape.PointingHandCursor if interactive else Qt.CursorShape.ArrowCursor)
        self.update()

    def set_theme(self, name):
        self.colors = theme.palette(name)
        self.update()

    # --- геометрия ---

    def geometry_(self):
        """(левый верх поля, сторона клетки, зазор)."""
        n = self.board.shape[0]
        side = min(self.width(), self.height()) - 8
        gap = max(4.0, side * (0.022 if n == 3 else 0.014))
        cell = (side - gap * (n + 1)) / n
        left = (self.width() - side) / 2
        top = (self.height() - side) / 2
        return QPointF(left, top), cell, gap, side

    def cell_rect(self, r, c):
        origin, cell, gap, _ = self.geometry_()
        return QRectF(origin.x() + gap + c * (cell + gap), origin.y() + gap + r * (cell + gap), cell, cell)

    def cell_at(self, pos):
        n = self.board.shape[0]
        for r in range(n):
            for c in range(n):
                if self.cell_rect(r, c).contains(pos):
                    return r, c
        return None

    # --- мышь ---

    def mouseMoveEvent(self, event):
        cell = self.cell_at(event.position()) if self.interactive else None
        if cell != self.hover:
            self.hover = cell
            self.update()

    def leaveEvent(self, event):
        self.hover = None
        self.update()

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.interactive:
            return
        cell = self.cell_at(event.position())
        if cell is not None:
            self.cellClicked.emit(*cell)

    # --- рисование ---

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        col = self.colors
        n = self.board.shape[0]
        origin, cell, gap, side = self.geometry_()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col["surface"]))
        p.drawRoundedRect(QRectF(origin.x(), origin.y(), side, side), gap * 2.2, gap * 2.2)

        line_cells = set(self.line or [])
        best = None
        if self.thoughts is not None and np.isfinite(self.thoughts).any():
            best = np.unravel_index(np.nanargmax(self.thoughts), self.thoughts.shape)
        radius = cell * 0.14
        for r in range(n):
            for c in range(n):
                rect = self.cell_rect(r, c)
                v = self.board[r, c]
                fill = QColor(col["tile"])
                if (r, c) == self.hover and v == 0:
                    fill = QColor(col["tile_hover"])
                if (r, c) in line_cells:
                    fill = mix(col["tile"], col["win"], 0.22)
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fill)
                p.drawRoundedRect(rect, radius, radius)
                if v == 0 and self.thoughts is not None and np.isfinite(self.thoughts[r, c]):
                    self._draw_thought(p, rect, float(self.thoughts[r, c]), (r, c) == best, radius)
                elif v == 0 and self.hints and n == 3 and self.interactive:
                    self._draw_hint(p, rect, r * 3 + c + 1)
                if v != 0:
                    self._draw_mark(p, rect, int(v), (r, c) == self.last and (r, c) not in line_cells)
                if v == 0 and (r, c) == self.hover and self.thoughts is None:
                    self._draw_ghost(p, rect)
        if self.line:
            self._draw_win_line(p)
        p.end()

    def _mark_pen(self, color, cell, alpha=255):
        c = QColor(color)
        c.setAlpha(alpha)
        pen = QPen(c, max(3.0, cell * 0.11))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        return pen

    def _draw_mark(self, p, rect, v, is_last):
        cell = rect.width()
        inset = cell * 0.24
        inner = rect.adjusted(inset, inset, -inset, -inset)
        if is_last:
            ring = QColor(self.colors["x" if v == 1 else "o"])
            ring.setAlpha(45)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(ring)
            p.drawRoundedRect(rect, cell * 0.14, cell * 0.14)
        p.setBrush(Qt.BrushStyle.NoBrush)
        if v == 1:
            p.setPen(self._mark_pen(self.colors["x"], cell))
            p.drawLine(inner.topLeft(), inner.bottomRight())
            p.drawLine(inner.topRight(), inner.bottomLeft())
        else:
            p.setPen(self._mark_pen(self.colors["o"], cell))
            p.drawEllipse(inner)

    def _draw_ghost(self, p, rect):
        """Полупрозрачная метка под мышью - куда встанет ход."""
        cell = rect.width()
        inset = cell * 0.3
        inner = rect.adjusted(inset, inset, -inset, -inset)
        mover = 1 if np.count_nonzero(self.board == 1) == np.count_nonzero(self.board == -1) else -1
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(self._mark_pen(self.colors["x" if mover == 1 else "o"], cell * 0.8, 70))
        if mover == 1:
            p.drawLine(inner.topLeft(), inner.bottomRight())
            p.drawLine(inner.topRight(), inner.bottomLeft())
        else:
            p.drawEllipse(inner)

    def _draw_hint(self, p, rect, digit):
        font = QFont(self.font())
        font.setPixelSize(max(10, int(rect.width() * 0.12)))
        p.setFont(font)
        p.setPen(QColor(self.colors["muted"]))
        pad = rect.width() * 0.08
        p.drawText(rect.adjusted(pad, pad * 0.6, -pad, -pad), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                   str(digit))

    def _draw_thought(self, p, rect, v, is_best, radius):
        col = self.colors
        tint = QColor(col["good"] if v >= 0 else col["bad"])
        tint.setAlpha(int(35 + 150 * min(1.0, abs(v))))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(tint)
        p.drawRoundedRect(rect, radius, radius)
        if is_best:
            pen = QPen(QColor(col["good"]), max(2.0, rect.width() * 0.035))
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
        font = QFont(self.font())
        font.setPixelSize(max(10, int(rect.width() * (0.16 if self.board.shape[0] == 3 else 0.22))))
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(col["text"]))
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{v:+.2f}".replace("-", "−"))

    def _draw_win_line(self, p):
        cells = sorted(self.line)
        a = self.cell_rect(*cells[0]).center()
        b = self.cell_rect(*cells[-1]).center()
        cell = self.cell_rect(0, 0).width()
        # чуть за центры крайних клеток
        dx, dy = b.x() - a.x(), b.y() - a.y()
        length = math.hypot(dx, dy) or 1.0
        ext = cell * 0.32
        a = QPointF(a.x() - dx / length * ext, a.y() - dy / length * ext)
        b = QPointF(b.x() + dx / length * ext, b.y() + dy / length * ext)
        color = QColor(self.colors["win"])
        color.setAlpha(225)
        pen = QPen(color, max(4.0, cell * 0.09))
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        p.setPen(pen)
        p.drawLine(a, b)
