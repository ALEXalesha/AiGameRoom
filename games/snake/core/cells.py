"""Кодировка клетки поля - общая для сети-мира, соперника и учителя.

Класс клетки (int8):
  0 пусто, 1 еда,
  2 голова змейки 0 (игрок), 3..6 тело змейки 0 с указателем на соседа ближе к голове,
  7 голова змейки 1 (сеть),  8..11 тело змейки 1 так же.
Указатель - направление UP/DOWN/LEFT/RIGHT (0..3). Почему указатели, а не «срок жизни»:
все правила становятся местными, а длина змейки перестаёт быть нужна (см. спек, п. 4).
"""
import numpy as np

UP, DOWN, LEFT, RIGHT, NONE = 0, 1, 2, 3, 4
DELTA = ((-1, 0), (1, 0), (0, -1), (0, 1))
OPPOSITE = (DOWN, UP, RIGHT, LEFT)

EMPTY, FOOD = 0, 1
HEAD = (2, 7)
BODY = (3, 8)          # тело змейки s с указателем d - класс BODY[s] + d
N_CLASSES = 12


def snake_of(cls):
    """Номер змейки клетки класса cls или None."""
    if 2 <= cls <= 6:
        return 0
    if 7 <= cls <= 11:
        return 1
    return None


def direction(a, b):
    """Направление из клетки a в соседнюю клетку b."""
    return DELTA.index((b[0] - a[0], b[1] - a[1]))


def build(h, w, snakes, food=()):
    """Поле по спискам клеток змеек (от хвоста к голове) и клеткам еды."""
    field = np.zeros((h, w), np.int8)
    for s, cells in enumerate(snakes):
        if not cells:
            continue
        for a, b in zip(cells, cells[1:]):
            field[a] = BODY[s] + direction(a, b)
        field[cells[-1]] = HEAD[s]
    for f in food:
        field[f] = FOOD
    return field


def head(field, s):
    found = np.argwhere(field == HEAD[s])
    return tuple(int(v) for v in found[0]) if len(found) else None


def body_cells(field, s):
    rs, cs = np.nonzero((field >= BODY[s]) & (field < BODY[s] + 4))
    return list(zip(rs.tolist(), cs.tolist()))


def pointer_target(field, cell, s):
    d = int(field[cell]) - BODY[s]
    return (cell[0] + DELTA[d][0], cell[1] + DELTA[d][1])


def heading(field, s):
    """Куда смотрит змейка: указатель шеи (клетки тела, указывающей на голову)."""
    h = head(field, s)
    for cell in body_cells(field, s):
        if pointer_target(field, cell, s) == h:
            return int(field[cell]) - BODY[s]
    return None


def tail(field, s):
    """Хвост - клетка тела, на которую не указывает ни одна клетка этой змейки."""
    cells = body_cells(field, s)
    pointed = {pointer_target(field, c, s) for c in cells}
    free = [c for c in cells if c not in pointed]
    return free[0] if len(free) == 1 else None


def chain(field, s):
    """Клетки змейки от хвоста к голове или None, если змейка разорвана."""
    t = tail(field, s)
    h = head(field, s)
    if t is None or h is None:
        return None
    out = [t]
    seen = {t}
    while out[-1] != h:
        cell = out[-1]
        if not (BODY[s] <= field[cell] < BODY[s] + 4):
            return None
        nxt = pointer_target(field, cell, s)
        if nxt in seen or not (0 <= nxt[0] < field.shape[0] and 0 <= nxt[1] < field.shape[1]):
            return None
        out.append(nxt)
        seen.add(nxt)
    return out if len(out) == 1 + len(body_cells(field, s)) else None


def length(field, s):
    return int(((field >= BODY[s]) & (field < BODY[s] + 4)).sum() + (field == HEAD[s]).sum())
