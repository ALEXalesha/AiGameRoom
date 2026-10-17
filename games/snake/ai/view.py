"""Что видит сеть-соперник: окно 15x15 вокруг своей головы и пара чисел.

Плоскости окна: 0 препятствие (любая змейка или край поля), 1 еда, 2 голова другой змейки,
3 своя шея (откуда пришла). Потом направление на ближайшую еду (dr/H, dc/W) и своё
направление (4). «Своя» и «чужая» змейка определяются номером s - одна сеть годится на
обе стороны, и для обучения примеры дают обе змейки.
"""
import numpy as np

from games.snake.core.cells import DELTA, EMPTY, FOOD, HEAD, head, heading

SIZE = 15
PAD = SIZE // 2
VIEW_LEN = SIZE * SIZE * 4 + 2 + 4


def view(field, s):
    H, W = field.shape
    h = head(field, s)
    d = heading(field, s)
    planes = np.zeros((H + 2 * PAD, W + 2 * PAD, 4), np.float32)
    planes[:, :, 0] = 1.0
    inner = planes[PAD:PAD + H, PAD:PAD + W]
    inner[:, :, 0] = (field != EMPTY) & (field != FOOD)
    inner[:, :, 1] = field == FOOD
    inner[:, :, 2] = field == HEAD[1 - s]
    if d is not None:
        inner[h[0] - DELTA[d][0], h[1] - DELTA[d][1], 3] = 1.0
    window = planes[h[0]:h[0] + SIZE, h[1]:h[1] + SIZE]

    out = np.zeros(VIEW_LEN, np.float32)
    out[:SIZE * SIZE * 4] = window.reshape(-1)
    foods = np.argwhere(field == FOOD)
    if len(foods):
        dist = np.abs(foods[:, 0] - h[0]) + np.abs(foods[:, 1] - h[1])
        f = foods[dist.argmin()]
        out[SIZE * SIZE * 4] = (f[0] - h[0]) / H
        out[SIZE * SIZE * 4 + 1] = (f[1] - h[1]) / W
    if d is not None:
        out[-4 + d] = 1.0
    return out
