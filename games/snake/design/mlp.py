"""Плотная сеть для сетей-оформителей: Dense - ReLU - ... - Dense, выход линейный или через
сигмоиду. Свои слои aikit.nn (numpy), сохранение в npz с размерами слоёв."""
import numpy as np

from aikit.nn import io
from aikit.nn.layers import Dense, ReLU, Sequential
from aikit.nn.losses import sigmoid


class MLP:
    def __init__(self, sizes, squash=False, rng=None):
        rng = np.random.default_rng(0) if rng is None else rng
        self.sizes = tuple(int(s) for s in sizes)
        self.squash = bool(squash)
        items = []
        for i, (a, b) in enumerate(zip(self.sizes, self.sizes[1:])):
            items.append(Dense(a, b, rng))
            if i < len(self.sizes) - 2:
                items.append(ReLU())
        self.net = Sequential(items)
        self.layers = {str(i): layer for i, layer in enumerate(items) if layer.params()}

    def params(self):
        return self.net.params()

    def forward(self, x):
        y = self.net.forward(np.asarray(x, np.float32))
        if self.squash:
            y = sigmoid(y)
            self._y = y
        return y

    def backward(self, dy):
        """dy - градиент по выходу (после сигмоиды, если она есть)."""
        if self.squash:
            dy = dy * self._y * (1 - self._y)
        return self.net.backward(dy.astype(np.float32))

    def save(self, path):
        arrays = io.collect(self.layers)
        arrays["meta.sizes"] = np.array(self.sizes)
        arrays["meta.squash"] = np.array([int(self.squash)])
        io.save(path, arrays)

    @classmethod
    def load(cls, path):
        arrays = io.load(path)
        net = cls([int(v) for v in arrays["meta.sizes"]], bool(arrays["meta.squash"][0]))
        io.restore(net.layers, arrays)
        for _, p, _ in net.params():
            if not np.all(np.isfinite(p)):
                raise ValueError(f"{path}: в весах не числа")
        return net
