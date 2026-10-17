"""Картинка поля из тайлов: ключ клетки и кодовое рисование тайла.

Ключ клетки - всё, от чего зависит её картинка: вид (пусто, еда, тело, голова, хвост), чья
змейка, связи с соседями (4 бита: вверх, вниз, влево, вправо), место в змейке t (8 уровней от
хвоста к голове - цвет и толщина), чётность клетки (шахматка), авария головы. Связи местные:
указатель клетки тела и соседи той же змейки, которые указывают в неё, - поэтому и разорванная
сбоем змейка рисуется по клеткам, как в 1.x.

Кодовый художник (code_tiles) - учитель сети-художника и её запасной вариант: QPainter рисует
тайл 24x24 так же, как Board 1.x рисовал змеек линиями от центра к центру, только каждая
клетка - свою половинку связи. Шум z слегка меняет «руку»: толщину, голову, глаза, еду.
"""
import numpy as np

from games.snake.core import cells
from games.snake.design.knobs import Z_DIM

TILE = 24
EMPTY, FOOD, BODY, HEAD, TAIL = range(5)
KINDS = 5
T_LEVELS = 8
FEATURES = KINDS + 2 + 4 + 1 + 1 + 1 + 3 + Z_DIM      # 21
N_KEYS = KINDS * 2 * 16 * T_LEVELS * 2 * 2


def encode(kind, snake=0, conn=0, t=0, parity=0, crashed=0):
    return ((((kind * 2 + snake) * 16 + conn) * T_LEVELS + t) * 2 + parity) * 2 + crashed


def decode(key):
    key = int(key)
    crashed, key = key % 2, key // 2
    parity, key = key % 2, key // 2
    t, key = key % T_LEVELS, key // T_LEVELS
    conn, key = key % 16, key // 16
    snake, kind = key % 2, key // 2
    return {"kind": kind, "snake": snake, "conn": conn, "t": t, "parity": parity, "crashed": crashed}


def group(key):
    """Вид клетки для закона «узнаётся»: 0 пусто, 1 еда, 2/3 тело и хвост змейки 0/1,
    4/5 голова змейки 0/1."""
    d = decode(key)
    if d["kind"] in (EMPTY, FOOD):
        return d["kind"]
    if d["kind"] == HEAD:
        return 4 + d["snake"]
    return 2 + d["snake"]


def key_grid(field, crashed=(False, False)):
    """Ключ каждой клетки поля (H, W) int32."""
    f = np.asarray(field).astype(np.int32)
    h, w = f.shape
    rr, cc = np.indices((h, w))
    kind = np.zeros((h, w), np.int32)
    snake = np.zeros((h, w), np.int32)
    conn = np.zeros((h, w), np.int32)
    t = np.zeros((h, w), np.int32)
    crash = np.zeros((h, w), np.int32)
    kind[f == cells.FOOD] = FOOD
    for s in (0, 1):
        body = (f >= cells.BODY[s]) & (f < cells.BODY[s] + 4)
        head = f == cells.HEAD[s]
        mine = body | head
        d = np.where(body, f - cells.BODY[s], -1)
        dp = np.full((h + 2, w + 2), -1, np.int32)
        dp[1:-1, 1:-1] = d
        incoming = np.zeros((h, w), np.int32)
        for e, (dy, dx) in enumerate(cells.DELTA):
            # сосед в стороне e - тело этой змейки и указывает обратно, в эту клетку
            nd = dp[1 + dy:1 + dy + h, 1 + dx:1 + dx + w]
            incoming |= (nd == cells.OPPOSITE[e]) * (1 << e)
        incoming &= np.where(mine, 15, 0)
        out = np.where(body, 1 << np.maximum(d, 0), 0)
        snake[mine] = s
        conn[mine] = (incoming | out)[mine]
        kind[body] = np.where(incoming[body] == 0, TAIL, BODY)
        kind[head] = HEAD
        crash[head] = int(bool(crashed[s]))
        t[head] = T_LEVELS - 1
        chain = cells.chain(f.astype(np.int8), s)
        if chain is not None and len(chain) > 1:
            n = len(chain) - 1
            for i, rc in enumerate(chain[:-1]):
                t[rc] = int(round((T_LEVELS - 1) * i / n))
        else:
            t[body] = np.where(incoming[body] == 0, 0, T_LEVELS - 1)
    parity = (rr + cc) % 2
    return ((((kind * 2 + snake) * 16 + conn) * T_LEVELS + t) * 2 + parity) * 2 + crash


def common_keys():
    """Ключи целых змеек, еды и пустых клеток - их художник рисует набором заранее."""
    out = []
    for p in (0, 1):
        out.append(encode(EMPTY, parity=p))
        out.append(encode(FOOD, parity=p))
        for s in (0, 1):
            for a in range(4):
                for b in range(a + 1, 4):
                    for t in range(T_LEVELS):
                        out.append(encode(BODY, s, (1 << a) | (1 << b), t, p))
                out.append(encode(TAIL, s, 1 << a, 0, p))
            for c in (0, 1, 2, 4, 8):
                for crash in (0, 1):
                    out.append(encode(HEAD, s, c, T_LEVELS - 1, p, crash))
    return np.asarray(out, np.int32)


def features(keys, palette, z):
    """Вход сети-художника (N, 21): вид, змейка, связи, t, чётность, авария, палитра, шум."""
    keys = np.asarray(keys).reshape(-1)
    x = np.zeros((len(keys), FEATURES), np.float32)
    z = np.asarray(z, np.float32).reshape(Z_DIM)
    for i, k in enumerate(keys):
        d = decode(k)
        x[i, d["kind"]] = 1
        if d["kind"] not in (EMPTY, FOOD):
            x[i, KINDS + d["snake"]] = 1
        for b in range(4):
            x[i, KINDS + 2 + b] = (d["conn"] >> b) & 1
        x[i, KINDS + 6] = d["t"] / (T_LEVELS - 1)
        x[i, KINDS + 7] = d["parity"]
        x[i, KINDS + 8] = d["crashed"]
        x[i, KINDS + 9 + int(palette)] = 1
    x[:, KINDS + 12:] = z
    return x


# --- кодовый художник ------------------------------------------------------------------------


def _hand(z):
    """«Рука» по шуму: толщина змейки, радиус головы, вынос глаз, размер еды."""
    z = np.clip(np.asarray(z, np.float64).reshape(Z_DIM), -1, 1)
    return {"stroke": 1 + 0.1 * z[0], "head": 0.47 + 0.03 * z[1], "eye": 0.16 + 0.04 * z[2],
            "food": 1 + 0.12 * z[3]}


def code_tiles(keys, palette, z, size=TILE):
    """Тайлы кода (N, size, size, 3) uint8 для ключей keys."""
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QRadialGradient

    from games.snake.ui.board import PALETTES, _mix

    pal = PALETTES[int(palette)]
    hand = _hand(z)
    keys = np.asarray(keys).reshape(-1)
    out = np.zeros((len(keys), size, size, 3), np.uint8)
    img = QImage(size, size, QImage.Format.Format_RGB32)
    cell = float(size)
    c = QPointF(cell / 2, cell / 2)
    for i, k in enumerate(keys):
        d = decode(k)
        img.fill(QColor(pal["cell_a"] if d["parity"] == 0 else pal["cell_b"]))
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setClipRect(QRectF(0, 0, cell, cell))
        kind, s = d["kind"], d["snake"]
        if kind == FOOD:
            base = QColor(pal["food"])
            glow = QColor(base)
            glow.setAlpha(55)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(glow)
            p.drawEllipse(c, cell * 0.5 * hand["food"], cell * 0.5 * hand["food"])
            r = cell * 0.33 * hand["food"]
            grad = QRadialGradient(c - QPointF(cell * 0.1, cell * 0.1), r * 1.2)
            grad.setColorAt(0, base.lighter(150))
            grad.setColorAt(1, base)
            p.setBrush(grad)
            p.drawEllipse(c, r, r)
            p.setBrush(QColor(255, 255, 255, 150))
            p.drawEllipse(c - QPointF(cell * 0.11, cell * 0.12), cell * 0.08, cell * 0.08)
        elif kind in (BODY, TAIL, HEAD):
            frac = 1.0 if kind == HEAD else d["t"] / (T_LEVELS - 1)
            color = _mix(pal["tail"][s], pal["body"][s], frac ** 0.7)
            width = cell * (0.52 + 0.24 * frac) * hand["stroke"]
            pen = QPen(color, width)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            p.setPen(pen)
            for b, (dy, dx) in enumerate(cells.DELTA):
                if d["conn"] >> b & 1:
                    p.drawLine(c, c + QPointF(dx, dy) * (cell / 2 + 1))
            p.setPen(Qt.PenStyle.NoPen)
            if kind != HEAD:
                p.setBrush(color)
                p.drawEllipse(c, width / 2, width / 2)
            else:
                p.setBrush(QColor(pal["head"][s]))
                p.drawEllipse(c, cell * hand["head"], cell * hand["head"])
                back = [b for b in range(4) if d["conn"] >> b & 1]
                fwd_d = cells.OPPOSITE[back[0]] if back else (cells.RIGHT if s == 0 else cells.LEFT)
                dy, dx = cells.DELTA[fwd_d]
                fwd = QPointF(dx, dy) * (cell * hand["eye"])
                side = QPointF(-dy, dx) * (cell * 0.2)
                p.setBrush(QColor(pal["eye"]))
                for sign in (-1, 1):
                    p.drawEllipse(c + fwd + side * sign, cell * 0.1, cell * 0.1)
                if d["crashed"]:
                    pen = QPen(QColor(pal["crash"]), max(2.0, cell * 0.12))
                    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                    p.setPen(pen)
                    p.setBrush(Qt.BrushStyle.NoBrush)
                    p.drawEllipse(c, cell * 0.44, cell * 0.44)
                    kk = cell * 0.24
                    p.drawLine(c + QPointF(-kk, -kk), c + QPointF(kk, kk))
                    p.drawLine(c + QPointF(-kk, kk), c + QPointF(kk, -kk))
        p.end()
        raw = np.frombuffer(img.constBits(), np.uint8).reshape(size, img.bytesPerLine() // 4, 4)
        out[i] = raw[:, :size, [2, 1, 0]]
    return out


def compose(tiles, grid):
    """Картинка поля (H*S, W*S, 3): tiles - словарь ключ -> тайл, grid - ключи клеток."""
    uniq, inv = np.unique(grid, return_inverse=True)
    stack = np.stack([tiles[int(k)] for k in uniq])
    h, w = grid.shape
    s = stack.shape[1]
    return np.ascontiguousarray(stack[inv.reshape(-1)].reshape(h, w, s, s, 3)
                                .transpose(0, 2, 1, 3, 4).reshape(h * s, w * s, 3))


class CodeTiles:
    """Источник тайлов для Board - кодовый художник (запасной вариант и вид без сетей)."""

    def __init__(self, z=None):
        self.z = np.zeros(Z_DIM) if z is None else np.asarray(z, np.float64)
        self.version = 0
        self._cache = {}

    def tiles(self, palette, keys):
        keys = np.asarray(keys).reshape(-1)
        need = [int(k) for k in keys if (palette, int(k)) not in self._cache]
        if need:
            for k, tile in zip(need, code_tiles(need, palette, self.z)):
                self._cache[palette, k] = tile
        return {int(k): self._cache[palette, int(k)] for k in keys}
