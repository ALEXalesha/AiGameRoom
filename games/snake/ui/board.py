"""Поле: рисует то, что выдала сеть-мир. Клетки - тайлы художника (с 2.0 - сеть-художник,
game/design; запасной и учитель - кодовый художник game/design/tiles.py), поверх - рамка,
полупрозрачная карта «где родится еда» (по желанию) и крупные надписи раунда кодом. Размер
поля берётся из самого поля; клетки всегда квадратные, поле по центру виджета.
"""
import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from games.snake.design.tiles import CodeTiles, compose, key_grid

PALETTES = [
    {"name": "Ночь", "bg": "#10141b", "cell_a": "#171d27", "cell_b": "#141923",
     "border": "#2a3342", "head": ("#9af7c1", "#ffc58a"), "body": ("#34d17c", "#ff8a3d"),
     "tail": ("#1d6b45", "#8a4a22"), "label": ("#7ee2a8", "#ffab6b"),
     "food": "#ff4d6d", "food_map": "#ffd54f", "crash": "#ff3b3b", "text": "#f2f5fa",
     "eye": "#0b0e13"},
    {"name": "Океан", "bg": "#0a1a26", "cell_a": "#0f2535", "cell_b": "#0c2130",
     "border": "#1f4058", "head": ("#c7f0ff", "#ffd1e3"), "body": ("#4fc3f7", "#f06292"),
     "tail": ("#1d5a78", "#7a2d4c"), "label": ("#7fd6fb", "#f48fb1"),
     "food": "#ffee58", "food_map": "#80deea", "crash": "#ff5252", "text": "#eef8ff",
     "eye": "#06131c"},
    {"name": "Светлая", "bg": "#efe9dc", "cell_a": "#e7e0d0", "cell_b": "#e2dac8",
     "border": "#c9bfa8", "head": ("#0e5a2a", "#10357f"), "body": ("#1f8a45", "#2456c7"),
     "tail": ("#8cc49e", "#9db3e6"), "label": ("#5fd08f", "#7fa4ff"),
     "food": "#d62828", "food_map": "#ff8c1a", "crash": "#b00020", "text": "#1d1d1d",
     "eye": "#ffffff"},
]

MARGIN = 10          # отступ поля от края виджета


def _mix(a, b, t):
    a, b = QColor(a), QColor(b)
    return QColor(round(a.red() + (b.red() - a.red()) * t),
                  round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class Board(QWidget):
    def __init__(self, parent=None, framed=True):
        super().__init__(parent)
        self.framed = framed
        self.field = None
        self.food_probs = None
        self.show_food_map = False
        self.crashed = (False, False)
        self.text = ""
        self.subtext = ""
        self.palette_index = 0
        self.overlay = None           # виджет паузы поверх поля (ставит экран матча)
        self._cells_cache = (None, None, None, None)
        self.tiles = CodeTiles()      # источник тайлов: tiles(палитра, ключи) -> {ключ: тайл}
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(320, 320)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

    # --- снаружи ---------------------------------------------------------------------

    def set_palette(self, index):
        self.palette_index = max(0, min(len(PALETTES) - 1, int(index)))
        self.update()

    def set_tiles(self, source):
        """Кто рисует клетки: сеть-художник (game/design/runtime) или кодовый художник."""
        self.tiles = source
        self._cells_cache = (None, None, None, None)
        self.update()

    def set_state(self, field, food_probs=None, show_food_map=False, crashed=(False, False),
                  text="", subtext=""):
        self.field = field
        self.food_probs = food_probs
        self.show_food_map = show_food_map
        self.crashed = crashed
        self.text = text
        self.subtext = subtext
        self.update()

    def shape(self):
        return self.field.shape if self.field is not None else (32, 32)

    def field_rect(self):
        """Квадрат поля в координатах виджета (под размер поля, клетки квадратные)."""
        h, w = self.shape()
        m = MARGIN if self.framed else 0
        cell = max(1.0, min((self.width() - 2 * m) / w, (self.height() - 2 * m) / h))
        fw, fh = cell * w, cell * h
        return QRectF((self.width() - fw) / 2, (self.height() - fh) / 2, fw, fh)

    def resizeEvent(self, event):
        if self.overlay is not None:
            self.overlay.setGeometry(self.rect())
        super().resizeEvent(event)

    # --- рисование ---------------------------------------------------------------------

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pal = PALETTES[self.palette_index]
        rect = self.field_rect()
        h, w = self.shape()
        cell = rect.width() / w
        radius = cell * 0.6
        if self.field is not None:
            # целые координаты: дробные включают медленный путь со сглаживанием
            p.drawPixmap(QPoint(round(rect.x()), round(rect.y())), self._cells(rect, cell))
        else:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(pal["bg"]))
            p.drawRoundedRect(rect, radius, radius)
        if self.framed:
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(pal["border"]), 2))
            p.drawRoundedRect(rect.adjusted(-1, -1, 1, 1), radius + 1, radius + 1)
        if self.field is not None:
            if self.show_food_map and self.food_probs is not None:
                clip = QPainterPath()
                clip.addRoundedRect(rect, cell * 0.6, cell * 0.6)
                p.setClipPath(clip)
                self._draw_food_map(p, rect, cell, pal)
                p.setClipping(False)
        if self.text:
            self._draw_text(p, rect, pal)
        p.end()

    def cells_image(self):
        """Клетки поля из тайлов (H*24, W*24, 3) uint8 - что рисует художник."""
        grid = key_grid(self.field, self.crashed)
        return compose(self.tiles.tiles(self.palette_index, np.unique(grid)), grid)

    def _cells(self, rect, cell):
        """Клетки поля картинкой нужного размера со скруглёнными углами. Картинка живёт между
        кадрами: после хода перерисовываются только клетки, у которых сменился ключ (обычно
        3-6), целиком - при новом размере, палитре или художнике."""
        ratio = self.devicePixelRatioF()
        h, w = self.field.shape
        base = (self.field.shape, self.palette_index, id(self.tiles), getattr(self.tiles, "version", 0),
                round(rect.width(), 2), ratio)
        state = (self.field.tobytes(), tuple(self.crashed))
        cache = self._cells_cache
        if cache[0] == base and cache[1] == state:
            return cache[2]
        grid = key_grid(self.field, self.crashed)
        if cache[0] == base:
            pix, prev = cache[2], cache[3]
            todo = np.argwhere(grid != prev)
        else:
            side = max(1, round(rect.width() * ratio)), max(1, round(rect.height() * ratio))
            pix = QPixmap(*side)
            pix.fill(Qt.GlobalColor.transparent)
            todo = np.argwhere(np.ones_like(grid, bool))
        if len(todo):
            tiles = self.tiles.tiles(self.palette_index, np.unique(grid[todo[:, 0], todo[:, 1]]))
            px = cell * ratio
            q = QPainter(pix)
            q.setRenderHint(QPainter.RenderHint.Antialiasing)
            q.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            clip = QPainterPath()
            clip.addRoundedRect(QRectF(0, 0, pix.width(), pix.height()), px * 0.6, px * 0.6)
            q.setClipPath(clip)
            images = {}
            xs = np.rint(np.arange(w + 1) * px).astype(int).tolist()
            ys = np.rint(np.arange(h + 1) * px).astype(int).tolist()
            for r, c in todo.tolist():
                k = int(grid[r, c])
                img = images.get(k)
                if img is None:
                    arr = np.ascontiguousarray(tiles[k])
                    img = QImage(arr.data, arr.shape[1], arr.shape[0], arr.shape[1] * 3,
                                 QImage.Format.Format_RGB888).copy()
                    images[k] = img
                q.drawImage(QRect(xs[c], ys[r], xs[c + 1] - xs[c], ys[r + 1] - ys[r]), img)
            q.end()
        pix.setDevicePixelRatio(ratio)
        self._cells_cache = (base, state, pix, grid)
        return pix

    def _draw_food_map(self, p, rect, cell, pal):
        probs = np.asarray(self.food_probs, dtype=np.float64)
        if probs.shape != self.field.shape or not np.all(np.isfinite(probs)):
            return
        # Яркость - во сколько раз вероятность выше равномерной: у обученной сети еда
        # «равномерно по пустым клеткам», и тогда поле ровно подсвечено везде, кроме змеек.
        ratio = probs * probs.size
        level = np.clip(ratio / 4.0, 0.0, 1.0)
        base = QColor(pal["food_map"])
        for r, c in np.argwhere(ratio > 0.05):
            color = QColor(base)
            color.setAlpha(int(12 + 170 * level[r, c]))
            p.fillRect(QRectF(rect.x() + c * cell, rect.y() + r * cell, cell, cell), color)

    def caption_layout(self, rect):
        """Шрифты и места крупной надписи поверх поля (отсчёт, итог раунда): крупный шрифт,
        мелкий, полоса-подложка, место главной строки и место подписи."""
        big = QFont(self.font())
        big.setPixelSize(max(18, int(rect.height() * 0.093)))
        big.setBold(True)
        small = QFont(self.font())
        small.setPixelSize(max(12, int(rect.height() * 0.045)))
        band_h = rect.height() * (0.2 if self.subtext else 0.15)
        band = QRectF(rect.x(), rect.center().y() - band_h / 2, rect.width(), band_h)
        main = QRectF(band.x(), band.y(), band.width(), band.height() * (0.68 if self.subtext else 1))
        sub = QRectF(band.x(), main.bottom() - band.height() * 0.08, band.width(), band.height() * 0.4)
        return big, small, band, main, sub

    def _draw_text(self, p, rect, pal):
        big, small, band, main, sub = self.caption_layout(rect)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 120))
        p.drawRect(band)
        p.setFont(big)
        p.setPen(QColor(0, 0, 0, 160))
        p.drawText(main.translated(2, 3), Qt.AlignmentFlag.AlignCenter, self.text)
        p.setPen(QColor("#ffffff"))
        p.drawText(main, Qt.AlignmentFlag.AlignCenter, self.text)
        if self.subtext:
            p.setFont(small)
            p.setPen(QColor(255, 255, 255, 210))
            p.drawText(sub, Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop, self.subtext)
