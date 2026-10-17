"""Сеть-художник: по ключу клетки, палитре и шуму рисует тайл 24x24 RGB.

    вход 21 (вид, змейка, связи, место в змейке, шахматка, авария, палитра, шум)
      -> Dense 384 -> ReLU -> Dense 384 -> ReLU -> Dense 1728 -> сигмоида = 24x24x3

Учится на тайлах кодового художника (game/design/tiles.code_tiles) при разном шуме - шум у
кода меняет толщину змейки, голову, глаза и еду, и сеть повторяет эту «руку». В игре тайлы
считаются одним пакетом на набор шума партии и кэшируются.
"""
import numpy as np

from games.snake.design.mlp import MLP
from games.snake.design.tiles import FEATURES, TILE, features

OUT = TILE * TILE * 3


class PainterNet:
    def __init__(self, hidden=384, rng=None, mlp=None):
        self.mlp = mlp if mlp is not None else MLP((FEATURES, hidden, hidden, OUT), squash=True, rng=rng)

    def params(self):
        return self.mlp.params()

    def forward(self, x):
        return self.mlp.forward(x)

    def backward(self, dy):
        return self.mlp.backward(dy)

    def draw(self, keys, palette, z):
        """Тайлы (N, 24, 24, 3) uint8."""
        y = self.forward(features(keys, palette, z))
        return np.clip(np.rint(y * 255), 0, 255).astype(np.uint8).reshape(-1, TILE, TILE, 3)

    def save(self, path):
        self.mlp.save(path)

    @classmethod
    def load(cls, path):
        mlp = MLP.load(path)
        if mlp.sizes[0] != FEATURES or mlp.sizes[-1] != OUT:
            raise ValueError(f"{path}: сеть не художника {mlp.sizes}")
        return cls(mlp=mlp)
