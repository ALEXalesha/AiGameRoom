"""Маленькая сеть на numpy, которая учится по ходу матча.

Вход - три последних раунда: ход человека, ход ИИ и исход, всё в one-hot
(3 * (2k + 3) чисел). Скрытый слой 24 с tanh, выход - k логитов, softmax.
После каждого раунда - один шаг Adam на новом примере и нескольких недавних (так сеть
не скачет от одного случая). Заранее сеть ничему не обучена: всё, что она знает, она
узнала о вас за этот матч.
"""
from collections import deque

import numpy as np

from aikit.nn.layers import Dense, Sequential, Tanh
from aikit.nn.losses import softmax, softmax_xent
from aikit.nn.optim import Adam
from games.rockpaper.ai.predictors import Predictor
from games.rockpaper.core.rules import outcome

DEPTH = 3
HIDDEN = 24
REPLAY = 7


class OnlineNet(Predictor):
    key = "net"

    def __init__(self, k, seed=0, lr=0.03, warmup=8):
        super().__init__(k)
        rng = np.random.default_rng(seed)
        self.width = 2 * k + 3
        self.n_in = DEPTH * self.width
        self.model = Sequential([Dense(self.n_in, HIDDEN, rng), Tanh(), Dense(HIDDEN, k, rng)])
        self.opt = Adam(self.model.params(), lr=lr)
        self.rounds = deque(maxlen=DEPTH)
        self.memory = deque(maxlen=60)          # (вход, ход человека)
        self.rng = np.random.default_rng(seed + 1)
        self.seen = 0
        self.warmup = warmup

    def features(self, rounds):
        x = np.zeros(self.n_in, np.float32)
        for i, (h, a) in enumerate(rounds):
            base = i * self.width
            x[base + h] = 1
            x[base + self.k + a] = 1
            x[base + 2 * self.k + 1 + outcome(h, a, self.k)] = 1
        return x

    def update(self, h, a):
        if len(self.rounds) == DEPTH:
            self.memory.append((self.features(self.rounds), h))
            self._train()
        self.rounds.append((h, a))
        self.seen += 1

    def _train(self):
        n = len(self.memory)
        idx = [n - 1]
        if n > 1:
            idx += list(self.rng.integers(0, n - 1, size=min(REPLAY, n - 1)))
        x = np.stack([self.memory[i][0] for i in idx])
        y = np.array([self.memory[i][1] for i in idx])
        logits = self.model.forward(x)
        _, grad = softmax_xent(logits, y)
        self.model.backward(grad)
        self.opt.step()

    def predict(self):
        if len(self.rounds) < DEPTH or self.seen < self.warmup:
            return None
        p = softmax(self.model.forward(self.features(self.rounds)[None]))[0]
        return [float(v) for v in p]

    def parameters(self):
        return sum(p.size for _, p, _ in self.model.params())
