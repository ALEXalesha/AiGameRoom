"""Боты - только соперники для проверок и статистики. Сеть у них не учится.

У любого игрока один метод: move(board) -> (строка, столбец) - ход того, чья очередь.
"""
from functools import lru_cache

import numpy as np

from games.tictactoe.core import rules


class RandomBot:
    name = "случайный"

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else np.random.default_rng()

    def move(self, board):
        moves = rules.legal_moves(board)
        return moves[self.rng.integers(len(moves))]


def winning_cells(board, player):
    """Клетки, ход в которые сразу даёт player победу."""
    n = board.shape[0]
    k = rules.win_length(n)
    flat = board.reshape(-1)
    idx = rules.lines(n, k)
    cells = flat[idx]
    ready = ((cells == player).sum(axis=1) == k - 1) & ((cells == 0).sum(axis=1) == 1)
    found = {int(line[cells_row == 0][0]) for line, cells_row in zip(idx[ready], cells[ready])}
    return [divmod(i, n) for i in sorted(found)]


class WinOrBlockBot:
    """Смотрит на один ход вперёд: выиграть, если можно; иначе закрыть клетку, которой
    соперник выиграл бы следующим ходом; иначе случайный ход."""
    name = "выиграй или помешай"

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else np.random.default_rng()

    def move(self, board):
        me = rules.to_move(board)
        for player in (me, -me):
            cells = winning_cells(board, player)
            if cells:
                return cells[self.rng.integers(len(cells))]
        moves = rules.legal_moves(board)
        return moves[self.rng.integers(len(moves))]


@lru_cache(maxsize=None)
def _negamax(key):
    """Исход для того, чья очередь, при лучшей игре обоих: 1, 0 или -1."""
    board = np.frombuffer(key, dtype=np.int8).reshape(3, 3)
    result = rules.outcome(board)
    if result is not None:
        return result * rules.to_move(board)
    return max(-_negamax(rules.play(board, cell).tobytes()) for cell in rules.legal_moves(board))


class MinimaxBot:
    """Полный перебор для 3x3: не проигрывает никогда. Из равных лучших ходов берёт
    случайный, чтобы партии против него были разными."""
    name = "минимакс"

    def __init__(self, rng=None):
        self.rng = rng if rng is not None else np.random.default_rng()

    def move(self, board):
        if board.shape != (3, 3):
            raise ValueError("минимакс только для поля 3x3")
        moves = rules.legal_moves(board)
        scores = [-_negamax(rules.play(board, cell).tobytes()) for cell in moves]
        best = max(scores)
        good = [m for m, s in zip(moves, scores) if s == best]
        return good[self.rng.integers(len(good))]


def play_game(x_player, o_player, n):
    """Одна партия. Возвращает (исход: 1 - X, -1 - O, 0 - ничья; список ходов)."""
    board = rules.new_board(n)
    moves = []
    while True:
        result = rules.outcome(board)
        if result is not None:
            return result, moves
        player = x_player if rules.to_move(board) == rules.X else o_player
        cell = player.move(board)
        board = rules.play(board, cell)
        moves.append(cell)


def match(player, opponent, n, games, colors="both"):
    """Серия партий с точки зрения player. colors: 'both' - половину за X, половину за O;
    'x' или 'o' - только этим цветом."""
    res = {"wins": 0, "losses": 0, "draws": 0, "games_as_x": 0, "games_as_o": 0}
    for g in range(games):
        as_x = colors == "x" or (colors == "both" and g % 2 == 0)
        if as_x:
            result, _ = play_game(player, opponent, n)
            res["games_as_x"] += 1
            mine = result
        else:
            result, _ = play_game(opponent, player, n)
            res["games_as_o"] += 1
            mine = -result
        res["wins" if mine > 0 else "losses" if mine < 0 else "draws"] += 1
    return res
