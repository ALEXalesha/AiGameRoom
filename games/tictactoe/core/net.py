"""Сеть оценки позиции после хода и выбор хода по ней.

Сеть смотрит на поле глазами того, кто только что сходил: свои = 1, чужие = -1, пусто = 0
(на входе - две плоскости «свои» и «чужие»). Выход - одно число в (-1, 1): ожидаемый исход
для сходившего, от проигрыша до победы. Ход - свободная клетка с наибольшей оценкой.
"""
import json

import numpy as np

from games.tictactoe.core import rules
from games.tictactoe.nn import io, layers


# --- симметрии поля: 4 поворота и 4 поворота отражённого ---


def transform(board, i):
    """Симметрия номер i (0..7) по двум последним осям; 0 - поле как есть."""
    b = np.flip(board, axis=-1) if i >= 4 else board
    return np.rot90(b, i % 4, axes=(-2, -1))


def untransform(board, i):
    """Обратная к transform(., i)."""
    b = np.rot90(board, -(i % 4), axes=(-2, -1))
    return np.flip(b, axis=-1) if i >= 4 else b


def symmetries(board):
    return np.stack([transform(board, i) for i in range(8)])


# --- вход сети ---


def perspective(boards, mover):
    """Пачка полей глазами игрока mover (1 или -1 на каждое поле): его камни станут 1."""
    return boards * np.asarray(mover, dtype=np.int8).reshape(-1, 1, 1)


def encode(boards):
    """(B, n, n) глазами своего -> (B, n, n, 2) float32: плоскость «свои», плоскость «чужие»."""
    boards = np.asarray(boards)
    return np.stack([boards == 1, boards == -1], axis=-1).astype(np.float32)


def afterstates(board):
    """Все ходы того, чья очередь: (список клеток, поля после хода глазами сходившего)."""
    cells = rules.legal_moves(board)
    mover = rules.to_move(board)
    after = np.repeat(board[None], len(cells), axis=0)
    for i, (r, c) in enumerate(cells):
        after[i, r, c] = mover
    return cells, after * np.int8(mover)


# --- сама сеть ---


class ValueNet:
    """3x3 - плотная 18 -> hidden -> hidden -> 1; 5x5 - свёртки 3x3 (2 -> channels x
    conv_layers) и плотный выход (head > 0 - ещё один скрытый плотный слой). Выход tanh."""

    def __init__(self, n, kind=None, rng=None, hidden=64, channels=32, conv_layers=3, head=0):
        rng = rng if rng is not None else np.random.default_rng()
        self.n = n
        self.kind = kind or ("dense" if n == 3 else "conv")
        self.config = {"n": n, "kind": self.kind, "hidden": hidden, "channels": channels,
                       "conv_layers": conv_layers, "head": head}
        items = []
        if self.kind == "dense":
            items += [layers.Flatten(), layers.Dense(2 * n * n, hidden, rng), layers.ReLU(),
                      layers.Dense(hidden, hidden, rng), layers.ReLU(),
                      layers.Dense(hidden, 1, rng)]
        else:
            cin = 2
            for _ in range(conv_layers):
                items += [layers.Conv3x3(cin, channels, rng), layers.ReLU()]
                cin = channels
            items.append(layers.Flatten())
            width = n * n * channels
            if head:
                items += [layers.Dense(width, head, rng), layers.ReLU()]
                width = head
            items.append(layers.Dense(width, 1, rng))
        items.append(layers.Tanh())
        self.body = layers.Sequential(items)

    def forward(self, planes):
        """Для обучения: (B, n, n, 2) -> (B, 1), запоминает всё для backward."""
        return self.body.forward(planes)

    def backward(self, dy):
        return self.body.backward(dy)

    def params(self):
        return self.body.params()

    def value(self, planes, chunk=4096):
        """Оценки пачки позиций (B,) - без обучения, кусками, чтобы не раздувать память."""
        out = [self.body.forward(planes[i:i + chunk])[:, 0] for i in range(0, len(planes), chunk)]
        return np.concatenate(out) if out else np.zeros(0, np.float32)

    def count(self):
        return int(sum(p.size for _, p, _ in self.params()))

    def save(self, path):
        arrays = io.collect({"net": self.body})
        arrays["meta"] = np.array(json.dumps(self.config))
        io.save(path, arrays)

    @classmethod
    def load(cls, path):
        arrays = io.load(path)
        config = json.loads(str(arrays.pop("meta")))
        model = cls(**config)
        io.restore({"net": model.body}, arrays)
        return model


def move_values(model, board):
    """Оценка каждой свободной клетки для того, чья очередь; занятые - NaN."""
    n = board.shape[0]
    vals = np.full((n, n), np.nan, dtype=np.float32)
    cells, after = afterstates(board)
    if cells:
        v = model.value(encode(after))
        for (r, c), x in zip(cells, v):
            vals[r, c] = x
    return vals


class NetPlayer:
    """Ход - свободная клетка с наибольшей оценкой сети."""
    name = "сеть"

    def __init__(self, model):
        self.model = model

    def move(self, board):
        cells, after = afterstates(board)
        v = self.model.value(encode(after))
        return cells[int(np.argmax(v))]
