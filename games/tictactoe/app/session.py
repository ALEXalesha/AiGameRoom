"""Партия человека против сети - без окна, чтобы проверять её тестами.

Кто за X: first = 'me' - человек, 'net' - сеть, 'alternate' - по очереди, начиная с
человека. X всегда ходит первым. Конец партии пишется в статистику ровно один раз.
"""
import numpy as np

from games.tictactoe.core import net, rules


class Session:
    def __init__(self, size, level, model, first="me", stats=None, stats_path=None):
        self.size = size
        self.level = level
        self.model = model
        self.first = first
        self.stats = stats
        self.stats_path = stats_path
        self.round = 0
        self.new_game()

    def new_game(self):
        if self.first == "me":
            self.human = rules.X
        elif self.first == "net":
            self.human = rules.O
        else:
            self.human = rules.X if self.round % 2 == 0 else rules.O
        self.board = rules.new_board(self.size)
        self.result = None
        self.line = None
        self.last = None
        self.recorded = False

    def restart(self):
        self.round += 1
        self.new_game()

    def to_move(self):
        return rules.to_move(self.board)

    def human_turn(self):
        return self.result is None and self.to_move() == self.human

    def _play(self, cell):
        self.board = rules.play(self.board, cell)
        self.last = cell
        self.result = rules.outcome(self.board)
        if self.result is not None:
            self.line = rules.winning_line(self.board)
            self.finish()

    def human_move(self, cell):
        """Ход человека; False - не его очередь, клетка занята или вне поля."""
        if not self.human_turn():
            return False
        r, c = cell
        if not (0 <= r < self.size and 0 <= c < self.size) or self.board[r, c] != 0:
            return False
        self._play((r, c))
        return True

    def net_move(self):
        if self.result is not None or self.to_move() == self.human:
            raise RuntimeError("сейчас не ход сети")
        cell = net.NetPlayer(self.model).move(self.board)
        self._play(cell)
        return cell

    def thoughts(self):
        """Оценка сети для каждой свободной клетки - за того, чья очередь; занятые - NaN."""
        if self.result is not None:
            return np.full(self.board.shape, np.nan, np.float32)
        return net.move_values(self.model, self.board)

    def outcome_for_human(self):
        if self.result is None:
            return None
        if self.result == 0:
            return "draw"
        return "win" if self.result == self.human else "loss"

    def finish(self):
        """Записать итог в статистику - один раз за партию."""
        if self.recorded or self.result is None or self.stats is None:
            return
        self.recorded = True
        self.stats.record(self.size, self.level, self.outcome_for_human())
        if self.stats_path is not None:
            self.stats.save(self.stats_path)
