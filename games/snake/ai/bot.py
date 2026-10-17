"""Бот, которому подражает сеть-соперник при обучении. В игре не участвует.

Ход выбирается по порядку важности: не подставляться под лобовое столкновение, не лезть в
область меньше своей длины (тупик), идти кратчайшим путём к еде, при прочих равных - туда,
где больше места.
"""
from collections import deque

import numpy as np

from games.snake.core.cells import DELTA, EMPTY, FOOD, OPPOSITE, head, heading, length

FLOOD_LIMIT = 200


def _free(field, cell):
    H, W = field.shape
    return 0 <= cell[0] < H and 0 <= cell[1] < W and field[cell] in (EMPTY, FOOD)


def _grid(field):
    """Поле списком «свободна ли клетка» по плоскому номеру - обход в ширину на списках
    Python в разы быстрее, чем с индексацией numpy на каждом шаге."""
    H, W = field.shape
    free = ((field == EMPTY) | (field == FOOD)).ravel().tolist()
    return H, W, free


def _neighbours(i, H, W):
    r, c = divmod(i, W)
    if r > 0:
        yield i - W
    if r < H - 1:
        yield i + W
    if c > 0:
        yield i - 1
    if c < W - 1:
        yield i + 1


def flood(field, start, limit=None, grid=None):
    """Сколько свободных клеток достижимо из start (включая её); с limit - счёт до limit."""
    if not _free(field, start):
        return 0
    H, W, free = grid or _grid(field)
    first = start[0] * W + start[1]
    seen = {first}
    queue = deque([first])
    while queue:
        for n in _neighbours(queue.popleft(), H, W):
            if free[n] and n not in seen:
                seen.add(n)
                if limit and len(seen) >= limit:
                    return len(seen)
                queue.append(n)
    return len(seen)


def food_distance(field, want=None, grid=None):
    """Расстояние в шагах от свободных клеток до ближайшей еды в обход препятствий:
    словарь {плоский номер: шаги}. С want - обход останавливается, когда все клетки из
    want найдены."""
    H, W, free = grid or _grid(field)
    dist = {}
    queue = deque()
    for f in np.flatnonzero(field.ravel() == FOOD).tolist():
        dist[f] = 0
        queue.append(f)
    left = set(want) - set(dist) if want else None
    while queue and (left is None or left):
        i = queue.popleft()
        for n in _neighbours(i, H, W):
            if free[n] and n not in dist:
                dist[n] = dist[i] + 1
                queue.append(n)
                if left is not None:
                    left.discard(n)
    return dist


def bot_move(field, s):
    h = head(field, s)
    d0 = heading(field, s)
    size = length(field, s)
    other = head(field, 1 - s)
    danger = set()
    if other is not None:
        danger = {(other[0] + dr, other[1] + dc) for dr, dc in DELTA}
    grid = _grid(field)
    W = field.shape[1]
    moves = []
    for d in range(4):
        if d == OPPOSITE[d0]:
            continue
        t = (h[0] + DELTA[d][0], h[1] + DELTA[d][1])
        if _free(field, t):
            moves.append((d, t))
    dist = food_distance(field, want={t[0] * W + t[1] for _, t in moves}, grid=grid)
    best, best_key = d0, None
    for d, t in moves:
        area = flood(field, t, limit=max(FLOOD_LIMIT, 2 * size), grid=grid)
        key = (t not in danger, area >= size, -dist.get(t[0] * W + t[1], 10 ** 6), area)
        if best_key is None or key > best_key:
            best, best_key = d, key
    return best
