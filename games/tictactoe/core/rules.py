"""Правила крестиков-ноликов - обычный код, сеть о них ничего не знает.

Поле - np.int8 N x N: 0 пусто, 1 крестик (X), -1 нолик (O). X ходит первым. Победа -
k своих подряд по строке, столбцу или диагонали: на 3x3 три, на 5x5 четыре.
"""
from functools import lru_cache

import numpy as np

X, O, EMPTY = 1, -1, 0
WIN_LENGTH = {3: 3, 5: 4}


def win_length(n):
    return WIN_LENGTH.get(n, min(n, 4))


def new_board(n):
    return np.zeros((n, n), dtype=np.int8)


@lru_cache(maxsize=None)
def _lines(n, k):
    found = []
    for r in range(n):
        for c in range(n):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                end_r, end_c = r + dr * (k - 1), c + dc * (k - 1)
                if 0 <= end_r < n and 0 <= end_c < n:
                    found.append([(r + dr * i) * n + (c + dc * i) for i in range(k)])
    return np.array(found, dtype=np.intp)


def lines(n, k=None):
    """Все отрезки длины k на поле n x n - номера клеток (строка * n + столбец)."""
    return _lines(n, k or win_length(n))


def winners(boards, k=None):
    """Победитель для пачки полей (B, n, n): 1, -1 или 0."""
    boards = np.asarray(boards)
    n = boards.shape[-1]
    k = k or win_length(n)
    sums = boards.reshape(len(boards), -1)[:, lines(n, k)].sum(axis=-1)
    return np.where((sums == k).any(axis=1), X, np.where((sums == -k).any(axis=1), O, 0)).astype(np.int8)


def winner(board):
    return int(winners(board[None])[0])


def winning_line(board):
    """Клетки выигрышной линии [(строка, столбец), ...] или None."""
    n = board.shape[0]
    k = win_length(n)
    sums = board.reshape(-1)[lines(n, k)].sum(axis=-1)
    hit = np.flatnonzero(np.abs(sums) == k)
    if len(hit) == 0:
        return None
    return [divmod(int(i), n) for i in lines(n, k)[hit[0]]]


def is_full(board):
    return bool(np.all(board != EMPTY))


def is_draw(board):
    return is_full(board) and winner(board) == 0


def outcome(board):
    """None - партия идёт; 1 или -1 - победитель; 0 - ничья."""
    w = winner(board)
    if w:
        return w
    return 0 if is_full(board) else None


def to_move(board):
    """Чей ход: X, если крестиков столько же, сколько ноликов."""
    return X if int(np.count_nonzero(board == X)) == int(np.count_nonzero(board == O)) else O


def legal_moves(board):
    return [divmod(int(i), board.shape[0]) for i in np.flatnonzero(board.reshape(-1) == EMPTY)]


def play(board, cell):
    """Новое поле после хода того, чья очередь. Старое поле не меняется."""
    n = board.shape[0]
    r, c = cell
    if not (0 <= r < n and 0 <= c < n):
        raise ValueError(f"клетка {cell} вне поля {n}x{n}")
    if board[r, c] != EMPTY:
        raise ValueError(f"клетка {cell} занята")
    if outcome(board) is not None:
        raise ValueError("партия уже закончилась")
    after = board.copy()
    after[r, c] = to_move(board)
    return after
