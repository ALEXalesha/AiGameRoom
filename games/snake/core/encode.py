"""Поле и ходы -> вход сети-мира (B, H, W, 23):
12 плоскостей класса клетки, 5 + 5 плоскостей хода змеек (одинаковых по всему полю),
1 плоскость «внутри поля» - за краем свёртка видит в ней ноль, так сеть знает, где стена.
"""
import numpy as np

from games.snake.core.cells import N_CLASSES

N_ACTIONS = 5
IN_CHANNELS = N_CLASSES + 2 * N_ACTIONS + 1


def encode(fields, a0, a1, dtype=np.float32):
    fields = np.asarray(fields)
    B, H, W = fields.shape
    x = np.zeros((B, H, W, IN_CHANNELS), dtype)
    np.put_along_axis(x, fields[..., None].astype(np.intp), 1.0, axis=-1)
    b = np.arange(B)
    x[b, :, :, N_CLASSES + np.asarray(a0)] = 1.0
    x[b, :, :, N_CLASSES + N_ACTIONS + np.asarray(a1)] = 1.0
    x[..., -1] = 1.0
    return x
