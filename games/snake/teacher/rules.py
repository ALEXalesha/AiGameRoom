"""Правила змейки обычным кодом - «учитель». Нужен только при обучении и в тестах: по нему
генерируются примеры для сети-мира и проверяется её точность. Игра его не импортирует.
"""
from typing import NamedTuple, Optional

import numpy as np

from games.snake.core.cells import BODY, DELTA, EMPTY, FOOD, HEAD, NONE, OPPOSITE, head, heading, tail


class Outcome(NamedTuple):
    field: Optional[np.ndarray]   # новое поле с новой едой; None - кто-то врезался
    moved: Optional[np.ndarray]   # новое поле до появления новой еды (цель сети-мира)
    ate: tuple
    crashed: tuple
    food: Optional[tuple]         # клетка новой еды или None


def resolve(field, s, action):
    """Направление хода: нажатое, а «нет нажатия» или разворот назад - прежнее."""
    h = heading(field, s)
    if action == NONE or action == OPPOSITE[h]:
        return h
    return action


def step(field, a0, a1, rng):
    H, W = field.shape
    dirs, heads, targets = [], [], []
    for s, a in enumerate((a0, a1)):
        d = resolve(field, s, a)
        h = head(field, s)
        dirs.append(d)
        heads.append(h)
        targets.append((h[0] + DELTA[d][0], h[1] + DELTA[d][1]))

    crashed = []
    for t in targets:
        outside = not (0 <= t[0] < H and 0 <= t[1] < W)
        crashed.append(outside or field[t] not in (EMPTY, FOOD))
    if targets[0] == targets[1]:
        crashed = [True, True]
    if any(crashed):
        return Outcome(None, None, (False, False), tuple(crashed), None)

    moved = field.copy()
    ate = []
    for s in (0, 1):
        t = targets[s]
        eats = field[t] == FOOD
        ate.append(bool(eats))
        if not eats:
            moved[tail(field, s)] = EMPTY
        moved[heads[s]] = BODY[s] + dirs[s]
        moved[t] = HEAD[s]

    new = moved
    food = None
    if any(ate):
        empties = np.argwhere(moved == EMPTY)
        if len(empties):
            food = tuple(int(v) for v in empties[rng.integers(len(empties))])
            new = moved.copy()
            new[food] = FOOD
    return Outcome(new, moved, tuple(ate), (False, False), food)
