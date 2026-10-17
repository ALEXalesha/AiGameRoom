"""Сеть-соперник: окно вокруг головы -> одно из 4 направлений.
Плотная сеть 906 -> 128 -> 64 -> 4. Ход выбирает сама сеть: никакой проверки «не в стену»
в игре нет - это она выучила."""
import numpy as np

from aikit.nn import io
from aikit.nn.layers import Dense, ReLU
from aikit.nn.losses import softmax
from games.snake.ai.view import VIEW_LEN, view


class PlayerNet:
    def __init__(self, sizes=(128, 64), rng=None, dtype=np.float32):
        rng = np.random.default_rng(0) if rng is None else rng
        self.sizes = tuple(sizes)
        dims = (VIEW_LEN, *sizes, 4)
        self.layers = {f"d{i}": Dense(a, b, rng, dtype) for i, (a, b) in enumerate(zip(dims, dims[1:]))}
        self.relus = [ReLU() for _ in sizes]

    def params(self):
        return [(f"{n}.{p}", a, g) for n, l in self.layers.items() for p, a, g in l.params()]

    def logits(self, x):
        dense = list(self.layers.values())
        for layer, relu in zip(dense, self.relus):
            x = relu.forward(layer.forward(x))
        return dense[-1].forward(x)

    def backward(self, d):
        dense = list(self.layers.values())
        d = dense[-1].backward(d)
        for layer, relu in zip(reversed(dense[:-1]), reversed(self.relus)):
            d = layer.backward(relu.backward(d))
        return d

    def probs(self, field, s):
        return softmax(self.logits(view(field, s)[None]).astype(np.float64))[0]

    def act(self, field, s, greedy=True, rng=None):
        p = self.probs(field, s)
        if greedy:
            return int(p.argmax())
        return int(rng.choice(4, p=p))

    def save(self, path):
        arrays = io.collect(self.layers)
        arrays["meta.sizes"] = np.array(self.sizes)
        io.save(path, arrays)

    @classmethod
    def load(cls, path):
        arrays = io.load(path)
        net = cls(tuple(int(v) for v in arrays["meta.sizes"]))
        io.restore(net.layers, arrays)
        return net
