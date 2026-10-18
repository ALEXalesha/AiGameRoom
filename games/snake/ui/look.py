"""Свой вид змейки - «террариум» (правило автора 17.10: меню, настройки и статистика у каждой
игры свои, на уровне Сапёра, Морского боя и BlockDrop).

- Главный экран: на весь фон - живая арена из клеток поля, по ней ползут две змейки (ваша
  зелёная и оранжевая сети), едят мигающую еду; под колонкой меню арена притушена. Фон
  тикает, только пока меню на экране (aikit.menu.Backdrop: pause/resume вкладки оболочки).
- Заголовок «Нейро-змейка» - Candara, буквы залиты градиентом кожи змейки с тёмной обводкой.
- «Играть» - голова змейки: на правом конце кнопки глаза.
- «Статистика» и «Настройки»: неподвижный фон-террариум (клетки поля к углу гаснут, вдоль
  низа - сброшенная кожа змейки), карточки полупрозрачные, заголовки разделов - Cascadia Code.

Расстановку элементов по-прежнему делает сеть-дизайнер (game/design), цвета и форма здесь и
в game/ui/theme.py - их видит и код-учитель дизайнера. Рисунок фона на раскладку не влияет.

Общий механизм - aikit.skin (Skin: палитра и фон страниц, законы page_problems/difference).
"""
import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QLinearGradient, QPainter, QPainterPath, QPen,
                           QRadialGradient)
from PySide6.QtWidgets import QLabel, QPushButton

from aikit.skin import Skin
from games.snake.design.knobs import scale_for  # noqa: F401 - масштаб окна (и вход сети-дизайнера)
from games.snake.ui import theme

SNAKES = {   # (голова, тело, хвост) двух змеек: ваша и сети - как на поле «Ночь»
    "dark": (("#b4ffd2", "#36d07f", "#155c38"), ("#ffd3a3", "#ff8a3d", "#7a3b14")),
    "light": (("#0e5a2a", "#25a35c", "#9fd3b0"), ("#7a3008", "#e8762b", "#f3c9a6")),
}
FOOD = {"dark": "#ff4d6d", "light": "#d62828"}


class SnakeSkin(Skin):
    key = "snake-terrarium"
    heading_family = "Candara"
    body_family = "Segoe UI"
    mono_family = "Cascadia Code"
    section_family = "Cascadia Code"
    radius = 14
    card_alpha = 228

    @property
    def palettes(self):
        out = {}
        for name in theme.THEMES:
            t = theme.TOKENS[name]
            out[name] = {"bg": t["bg"], "surface": t["card"], "surface2": t["button"], "border": t["line"],
                         "text": t["text"], "muted": t["muted"], "accent": t["accent"],
                         "accent_text": t["accent_text"], "good": t["good"], "bad": t["bad"], "warn": t["mid"],
                         "grid": t["line"]}
        return out

    def paint_backdrop(self, p, w, h, pal, theme_name):
        paint_terrarium(p, w, h, theme_name)


SKIN = SnakeSkin()


def cell_size(h):
    return max(26, round(h / 22))


def paint_terrarium(p, w, h, theme_name):
    """Неподвижный фон страниц: клетки поля, гаснущие от правого нижнего угла, и сброшенная кожа
    змейки вдоль низа."""
    t = theme.TOKENS[theme_name if theme_name in theme.TOKENS else "dark"]
    p.fillRect(0, 0, w, h, QColor(t["bg"]))
    c = cell_size(h)
    cell = QColor(t["line"])
    far = math.hypot(w, h)
    for y in range(0, h, c):
        for x in range(0, w, c):
            if (x // c + y // c) % 2:
                continue
            d = math.hypot(w - x, h - y) / far
            a = max(0.0, 1.0 - d * 1.6)
            if a <= 0.02:
                continue
            cell.setAlphaF(0.55 * a)
            p.fillRect(x, y, c, c, cell)
    # сброшенная кожа: волна из сегментов вдоль низа, бледнее к хвосту
    head, body, tail = SNAKES[theme_name if theme_name in SNAKES else "dark"][0]
    pts = []
    n = max(12, w // max(1, c // 2))
    for i in range(n + 1):
        x = w * (0.06 + 0.9 * i / n)
        y = h - c * 1.6 - math.sin(i / n * math.pi * 3.0) * c * 0.9
        pts.append(QPointF(x, y))
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    for i, pt in enumerate(pts):
        k = i / n
        col = QColor(tail if k < 0.5 else body)
        col.setAlphaF(0.10 + 0.16 * k)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(col)
        r = c * (0.22 + 0.16 * k)
        p.drawEllipse(pt, r, r)


class Arena:
    """Живая арена меню: клетки и две змейки, ползущие по кольцам; еда на пути впереди."""

    STEP = 0.11          # секунд на клетку
    LENGTH = (14, 11)

    def __init__(self):
        self._key = None
        self.paths = []

    def _paths(self, w, h):
        c = cell_size(h)
        cols, rows = w // c + 1, h // c + 1
        key = (cols, rows, c)
        if key == self._key:
            return c
        self._key = key

        def ring(x0, y0, x1, y1, clockwise=True):
            path = [(x, y0) for x in range(x0, x1)] + [(x1, y) for y in range(y0, y1)]
            path += [(x, y1) for x in range(x1, x0, -1)] + [(x0, y) for y in range(y1, y0, -1)]
            return path if clockwise else path[::-1]
        m = 2
        self.paths = [ring(m, m, cols - 1 - m, rows - 1 - m),
                      ring(m + 3, m + 3, cols - 1 - m - 3, rows - 1 - m - 3, clockwise=False)]
        return c

    def paint(self, p, w, h, t, theme_name):
        tk = theme.TOKENS[theme_name if theme_name in theme.TOKENS else "dark"]
        c = self._paths(w, h)
        p.fillRect(0, 0, w, h, QColor(tk["bg"]))
        a = QColor(tk["line"])
        a.setAlphaF(0.45)
        b = QColor(tk["line"])
        b.setAlphaF(0.22)
        for y in range(0, h + c, c):
            for x in range(0, w + c, c):
                p.fillRect(x, y, c, c, a if (x // c + y // c) % 2 else b)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = SNAKES[theme_name if theme_name in SNAKES else "dark"]
        food = QColor(FOOD.get(theme_name, FOOD["dark"]))
        for k, path in enumerate(self.paths):
            if len(path) < 8:
                continue
            n = len(path)
            moved = t / self.STEP + k * n * 0.37
            head = int(moved) % n
            frac = moved - int(moved)
            length = self.LENGTH[k]
            # еда - на 9 клеток впереди головы, пульсирует
            fx, fy = path[(head + 9 + (int(moved) // 25) % 7) % n]
            pulse = 0.5 + 0.5 * math.sin(t * 6 + k)
            glow = QRadialGradient(QPointF((fx + 0.5) * c, (fy + 0.5) * c), c * 0.9)
            g = QColor(food)
            g.setAlphaF(0.45 * pulse)
            glow.setColorAt(0, g)
            g.setAlphaF(0.0)
            glow.setColorAt(1, g)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(glow))
            p.drawEllipse(QPointF((fx + 0.5) * c, (fy + 0.5) * c), c * 0.9, c * 0.9)
            p.setBrush(food)
            p.drawEllipse(QPointF((fx + 0.5) * c, (fy + 0.5) * c), c * 0.26, c * 0.26)
            hc, bc, tc = (QColor(x) for x in colors[k])
            pts = []
            for i in range(length + 1):
                j = (head - i) % n
                x0, y0 = path[j]
                x1, y1 = path[(j + 1) % n]
                pts.append(QPointF((x0 + (x1 - x0) * frac + 0.5) * c, (y0 + (y1 - y0) * frac + 0.5) * c))
            for i in range(len(pts) - 1, 0, -1):
                q = i / length
                col = _mix(bc, tc, q)
                p.setPen(QPen(col, c * (0.62 - 0.22 * q), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                p.drawLine(pts[i], pts[i - 1])
            hx, hy = pts[0].x(), pts[0].y()
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(hc)
            p.drawEllipse(QPointF(hx, hy), c * 0.4, c * 0.4)
            dx, dy = pts[0].x() - pts[1].x(), pts[0].y() - pts[1].y()
            norm = math.hypot(dx, dy) or 1.0
            dx, dy = dx / norm, dy / norm
            eye = QColor("#0b0e13" if theme_name != "light" else "#ffffff")
            p.setBrush(eye)
            for s in (-1, 1):
                p.drawEllipse(QPointF(hx + dx * c * 0.14 - dy * s * c * 0.17, hy + dy * c * 0.14 + dx * s * c * 0.17),
                              c * 0.08, c * 0.08)
        # колонку меню не перебивать: середина притушена
        veil = QRadialGradient(QPointF(w / 2, h * 0.48), max(w, h) * 0.55)
        v = QColor(tk["bg"])
        light = theme_name == "light"
        v.setAlphaF(0.8 if light else 0.88)
        veil.setColorAt(0, v)
        v.setAlphaF(0.35 if light else 0.55)
        veil.setColorAt(0.55, v)
        v.setAlphaF(0.0)
        veil.setColorAt(1, v)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(veil))
        p.drawRect(QRectF(0, 0, w, h))


def _mix(a, b, t):
    return QColor(round(a.red() + (b.red() - a.red()) * t), round(a.green() + (b.green() - a.green()) * t),
                  round(a.blue() + (b.blue() - a.blue()) * t))


class SnakeTitle(QLabel):
    """Заголовок меню: шрифт и размер - из таблицы стилей (QLabel#title), рисунок свой - буквы
    залиты градиентом кожи змейки, тёмная обводка и тень. Размер - как у обычной метки (его
    видит сеть-дизайнер)."""

    def __init__(self):
        super().__init__("")
        self.setObjectName("title")
        self.theme_name = "dark"

    def paintEvent(self, event):
        text = self.text()
        if not text:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = self.font()
        fm = self.fontMetrics()
        x = (self.width() - fm.horizontalAdvance(text)) / 2
        y = (self.height() + fm.ascent() - fm.descent()) / 2
        path = QPainterPath()
        path.addText(QPointF(x, y), f, text)
        head, body, tail = SNAKES[self.theme_name if self.theme_name in SNAKES else "dark"][0]
        shadow = QColor("#000000" if self.theme_name != "light" else "#7a8f74")
        shadow.setAlphaF(0.45)
        p.translate(0, max(2.0, f.pixelSize() / 22 if f.pixelSize() > 0 else 3.0))
        p.fillPath(path, shadow)
        p.translate(0, -max(2.0, f.pixelSize() / 22 if f.pixelSize() > 0 else 3.0))
        grad = QLinearGradient(0, y - fm.ascent(), 0, y)
        grad.setColorAt(0.0, QColor(head))
        grad.setColorAt(0.55, QColor(body))
        grad.setColorAt(1.0, QColor(tail))
        p.fillPath(path, QBrush(grad))
        p.setPen(QPen(QColor(tail).darker(160), max(1.0, fm.height() / 40)))
        p.drawPath(path)
        p.end()


class HeadButton(QPushButton):
    """«Играть» - голова змейки: глаза на правом конце кнопки."""

    def __init__(self, text=""):
        super().__init__(text)
        self.setObjectName("primary")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.eye = QColor("#04130a")

    def paintEvent(self, event):
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = max(2.5, self.height() * 0.085)
        cx = self.width() - self.height() * 0.42
        cy = self.height() / 2
        for s in (-1, 1):
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor("#ffffff"))
            p.drawEllipse(QPointF(cx, cy + s * r * 1.6), r * 1.25, r * 1.25)
            p.setBrush(self.eye)
            p.drawEllipse(QPointF(cx + r * 0.35, cy + s * r * 1.6), r * 0.7, r * 0.7)
        p.end()

