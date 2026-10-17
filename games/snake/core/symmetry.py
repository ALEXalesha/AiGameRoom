"""Восемь симметрий поля (4 поворота x отражение) для сети-мира.

Правила змейки не меняются, если поле повернуть или отразить: меняются только имена
направлений. Поэтому сеть можно спросить о всех восьми видах поля сразу и сложить ответы,
вернув их в исходную геометрию. Редкие ошибки сети в разных видах не совпадают и гасятся:
на отложенных полях 32x32 один проход совпадал с правилами на 99,78% ходов, восемь - на
100% (замер 26.09.2026). Кода правил здесь нет: только перестановка клеток и имён.
"""
import numpy as np

from games.snake.core.cells import BODY, DELTA, N_CLASSES, NONE

TRANSFORMS = tuple((k, flip) for flip in (False, True) for k in range(4))


def apply(a, k, flip):
    """Преобразовать поле (или поле с каналами последней осью)."""
    a = np.fliplr(a) if flip else a
    return np.rot90(a, k, axes=(0, 1))


def undo(a, k, flip):
    a = np.rot90(a, -k, axes=(0, 1))
    return np.fliplr(a) if flip else a


def direction_perm(k, flip):
    """Куда переходит каждое из направлений UP, DOWN, LEFT, RIGHT при преобразовании."""
    perm = []
    for dr, dc in DELTA:
        g = np.zeros((3, 3), int)
        g[1, 1] = 1
        g[1 + dr, 1 + dc] = 2
        h = apply(g, k, flip)
        c, n = np.argwhere(h == 1)[0], np.argwhere(h == 2)[0]
        perm.append(DELTA.index((int(n[0] - c[0]), int(n[1] - c[1]))))
    return tuple(perm)


def class_map(perm):
    """Класс клетки -> класс той же клетки в преобразованном поле (указатели тела меняются)."""
    m = np.arange(N_CLASSES)
    for s in (0, 1):
        for d in range(4):
            m[BODY[s] + d] = BODY[s] + perm[d]
    return m


def action(a, perm):
    return a if a == NONE else perm[a]


VIEWS = tuple((k, flip, direction_perm(k, flip), class_map(direction_perm(k, flip))) for k, flip in TRANSFORMS)
