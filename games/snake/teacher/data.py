"""Примеры для сети-мира: партии учителя и случайно выращенные поля.

Партии ведут простые боты с разной долей случайных ходов - так в данных есть и длинные
змейки, и столкновения всех видов. Выращенные поля дают расположения, до которых боты
сами не доводят (змейки, свёрнутые в клубок, головы у чужих хвостов).
"""
from typing import NamedTuple

import numpy as np

from games.snake.teacher.rules import step
from games.snake.core.cells import DELTA, EMPTY, FOOD, NONE, OPPOSITE, build, head, heading, tail
from games.snake.core.encode import encode
from games.snake.core.start import start_field

CHANGE_WEIGHT = 20.0
SNAKE_WEIGHT = 5.0


def grow(field, s, length, rng):
    """Случайное блуждание по пустым клеткам: змейка s длиной до length клеток
    (не меньше 2). Возвращает False, если не вышло."""
    H, W = field.shape
    empties = np.argwhere(field == EMPTY)
    if not len(empties):
        return False
    cell = tuple(int(v) for v in empties[rng.integers(len(empties))])
    cells = [cell]
    taken = {cell}
    while len(cells) < length:
        r, c = cells[-1]
        options = [(r + dr, c + dc) for dr, dc in DELTA
                   if 0 <= r + dr < H and 0 <= c + dc < W
                   and field[r + dr, c + dc] == EMPTY and (r + dr, c + dc) not in taken]
        if not options:
            break
        nxt = options[rng.integers(len(options))]
        cells.append(nxt)
        taken.add(nxt)
    if len(cells) < 2:
        return False
    snake = build(H, W, [cells] if s == 0 else [[], cells])
    mask = snake != EMPTY
    field[mask] = snake[mask]
    return True


def random_field(rng, h, w, max_len=None):
    max_len = max_len or h * w // 4
    while True:
        field = np.zeros((h, w), np.int8)
        ok = all(grow(field, s, int(rng.integers(2, max_len + 1)), rng) for s in (0, 1))
        if not ok:
            continue
        for _ in range(int(rng.integers(0, 3))):
            empties = np.argwhere(field == EMPTY)
            if len(empties):
                field[tuple(empties[rng.integers(len(empties))])] = FOOD
        return field


def greedy_move(field, s, rng, noise):
    """Бот для данных: безопасный ход ближе к еде; с долей noise - любой ход, включая
    «нет нажатия» и разворот (сеть должна знать, что они значат)."""
    if rng.random() < noise:
        return int(rng.integers(0, 5))
    H, W = field.shape
    h = head(field, s)
    d0 = heading(field, s)
    foods = np.argwhere(field == FOOD)
    best, best_score = NONE, None
    for d in range(4):
        if d == OPPOSITE[d0]:
            continue
        t = (h[0] + DELTA[d][0], h[1] + DELTA[d][1])
        if not (0 <= t[0] < H and 0 <= t[1] < W) or field[t] not in (EMPTY, FOOD):
            continue
        dist = min((abs(t[0] - f[0]) + abs(t[1] - f[1]) for f in foods), default=0)
        score = dist + rng.random() * 0.5
        if best_score is None or score < best_score:
            best, best_score = d, score
    return best


class Sample(NamedTuple):
    field: np.ndarray
    a0: int
    a1: int
    moved: np.ndarray    # цель поля (до новой еды); у столкновения - копия field
    events: np.ndarray   # ate0, ate1, crash0, crash1
    food: int            # номер клетки новой еды или -1


def play(rng, h, w, n, max_len=None):
    """n примеров с поля h x w: партии от стартового или выращенного поля."""
    out = []
    while len(out) < n:
        field = start_field(h, w) if rng.random() < 0.3 else random_field(rng, h, w, max_len)
        if not (field == FOOD).any():
            empties = np.argwhere(field == EMPTY)
            field[tuple(empties[rng.integers(len(empties))])] = FOOD
        noise = (float(rng.uniform(0, 0.5)), float(rng.uniform(0, 0.5)))
        for _ in range(4 * (h + w)):
            a0 = greedy_move(field, 0, rng, noise[0])
            a1 = greedy_move(field, 1, rng, noise[1])
            o = step(field, a0, a1, rng)
            events = np.array([*o.ate, *o.crashed], np.float32)
            food = -1 if o.food is None else o.food[0] * w + o.food[1]
            moved = field.copy() if o.field is None else o.moved
            out.append(Sample(field, a0, a1, moved, events, food))
            if o.field is None or len(out) >= n:
                break
            field = o.field
    return out


def tensors(samples):
    """Сэмплы одного размера поля -> входы и цели для обучения."""
    fields = np.stack([s.field for s in samples])
    moved = np.stack([s.moved for s in samples])
    x = encode(fields, np.array([s.a0 for s in samples]), np.array([s.a1 for s in samples]))
    events = np.stack([s.events for s in samples])
    crash = events[:, 2:].max(axis=1) > 0
    changed = fields != moved
    near = changed.copy()
    near[:, 1:] |= changed[:, :-1]
    near[:, :-1] |= changed[:, 1:]
    near[:, :, 1:] |= changed[:, :, :-1]
    near[:, :, :-1] |= changed[:, :, 1:]
    # Хвосты - всегда с весом: у съевшей змейки хвост не меняется, а правило «хвост
    # остаётся» самое редкое и единственное дальнее (без веса - половина ошибок сети).
    for b, s in enumerate(samples):
        for k in (0, 1):
            t = tail(s.field, k)
            if t is not None:
                near[b][t] = True
    # Клетки змеек - с весом: «тело остаётся телом» самое частое правило, и без веса сеть
    # изредка принимала клетку свёрнутой змейки за хвост и стирала (замер 26.09).
    snake = (fields >= 2)
    weight = np.where(near, CHANGE_WEIGHT, np.where(snake, SNAKE_WEIGHT, 1.0)).astype(np.float32)
    weight[crash] = 0.0
    ev_weight = np.ones_like(events)
    ev_weight[crash, :2] = 0.0     # «съела» на ходу со столкновением не нужно
    food = np.array([max(s.food, 0) for s in samples])
    food_mask = np.array([s.food >= 0 for s in samples], np.float32)
    return x, moved.astype(np.intp), weight, events, ev_weight, food, food_mask
