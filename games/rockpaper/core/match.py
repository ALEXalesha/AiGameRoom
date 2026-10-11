"""Матч без Qt: раунды, счёт, фиксация хода ИИ до хода человека.

Порядок раунда:
    m.prepare(ai)   - ИИ выбирает ход по истории прошлых раундов, ход закрыт хэшем;
    m.play(human)   - человек ходит, ход ИИ раскрывается, раунд пишется в историю.

ИИ получает только историю прошлых раундов (Round без ключей) - закон-тест в
tests/test_honesty.py.
"""
from dataclasses import dataclass, field

from games.rockpaper.core import commit as cm
from games.rockpaper.core.rules import LOSS, TIE, WIN, check_k, outcome

LENGTHS = (50, 100, 0)          # 0 - без конца


@dataclass(frozen=True)
class Round:
    human: int
    ai: int
    result: int                 # для человека: WIN, TIE, LOSS


@dataclass
class Pending:
    round_no: int
    move: int
    nonce: str
    commit: str
    thoughts: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Reveal:
    round_no: int
    human: int
    ai: int
    result: int
    nonce: str
    commit: str
    thoughts: dict

    def verified(self, k):
        return cm.verify(self.commit, k, self.round_no, self.ai, self.nonce)


class Match:
    def __init__(self, k=3, length=100):
        self.k = check_k(k)
        if length < 0:
            raise ValueError(length)
        self.length = length
        self.rounds = []
        self.reveals = []
        self.pending = None
        self.ended = False      # бесконечный матч закончен кнопкой

    @property
    def over(self):
        return self.ended or (self.length > 0 and len(self.rounds) >= self.length)

    def history(self):
        return tuple(self.rounds)

    def prepare(self, ai):
        """ИИ выбирает ход до хода человека. Повторный вызов в том же раунде ничего не меняет."""
        if self.over:
            raise RuntimeError("матч окончен")
        if self.pending is None:
            move, thoughts = ai.choose(self.history())
            if not 0 <= move < self.k:
                raise ValueError(f"ИИ выбрал ход {move}")
            h, nonce = cm.commit(self.k, len(self.rounds), move)
            self.pending = Pending(len(self.rounds), move, nonce, h, thoughts)
        return self.pending.commit

    def play(self, human, ai=None):
        """Ход человека. Возвращает Reveal. ai - чтобы ИИ узнал итог раунда (обучение)."""
        if self.pending is None:
            raise RuntimeError("ИИ ещё не выбрал ход: сначала prepare()")
        if not 0 <= human < self.k:
            raise ValueError(f"нет хода {human}")
        p = self.pending
        r = Round(human, p.move, outcome(human, p.move, self.k))
        self.rounds.append(r)
        rv = Reveal(p.round_no, human, p.move, r.result, p.nonce, p.commit, p.thoughts)
        self.reveals.append(rv)
        self.pending = None
        if ai is not None:
            ai.observe(r)
        return rv

    def end(self):
        self.ended = True
        self.pending = None

    def score(self):
        """{'wins', 'ties', 'losses'} - для человека."""
        res = [r.result for r in self.rounds]
        return {"wins": res.count(WIN), "ties": res.count(TIE), "losses": res.count(LOSS)}

    def ai_share_curve(self):
        """Доля побед ИИ после каждого раунда (по всем раундам)."""
        out, ai_wins = [], 0
        for i, r in enumerate(self.rounds, 1):
            ai_wins += r.result == LOSS
            out.append(ai_wins / i)
        return out

    def human_share_curve(self):
        out, wins = [], 0
        for i, r in enumerate(self.rounds, 1):
            wins += r.result == WIN
            out.append(wins / i)
        return out

    def outcome_for_human(self):
        """'win' / 'loss' / 'draw' по счёту раундов, пока матч не окончен - None."""
        if not self.over or not self.rounds:
            return None
        s = self.score()
        if s["wins"] > s["losses"]:
            return "win"
        if s["wins"] < s["losses"]:
            return "loss"
        return "draw"
