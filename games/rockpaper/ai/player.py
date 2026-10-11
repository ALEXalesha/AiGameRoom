"""ИИ: набор предсказателей, мета-выбор и защита от того, что его самого раскусят.

Стратегия - предсказатель плюс сдвиг j. Сдвиг 0: «человек сыграет, как предсказано» -
ИИ бьёт предсказанное. Сдвиг j: «человек на j шагов хитрее» - распределение повёрнуто
на j (на трёх знаках сдвиг 1 значит «человек сыграет то, что бьёт предсказанное», 2 -
«то, что бьёт и это»). Так ИИ ловит и того, кто сам пытается его предсказать.

После каждого раунда у каждой стратегии счёт: итог её хода против настоящего хода
человека, с затуханием (последние раунды важнее). Ходит лучшая стратегия. Если ни у
одной нет преимущества (счёт не выше порога), ИИ ходит случайно: случайный ход нельзя
обыграть.

Защита: если ИИ в последних раундах проигрывает заметно чаще, чем выигрывает, его
раскусили - он уходит в случайные ходы на guard_len раундов. Повторное срабатывание
вскоре после прошлого удваивает срок.

ИИ видит только историю прошлых раундов: choose(history) - и ничего больше.
"""
import random
from collections import deque

import numpy as np

from games.rockpaper.ai import predictors as P
from games.rockpaper.core.rules import LOSS, WIN, best_responses, check_k, outcome

LEVELS = ("novice", "medium", "strong")


class AiPlayer:
    # Горизонты памяти мета-выбора: у каждого свой «судья», который ведёт счёт стратегий с
    # таким затуханием. Короткая память быстро ловит смену привычки, длинная не путает
    # везение с закономерностью. Каким судьям верить, решает их собственный счёт.
    DECAYS = (0.7, 0.9, 0.97, 0.995)
    JUDGE_DECAY = 0.98

    # Уверенность: счёт лучшего судьи ниже LO - ход случайный, выше HI - всегда по прогнозу,
    # между ними - по прогнозу с долей (счёт - LO) / (HI - LO). Против случайного игрока
    # счёт судей - шум, и ИИ почти всё время ходит случайно: в его ходах нет закономерности,
    # которую можно было бы поймать.
    SURE_LO = 1.5
    SURE_HI = 5.0
    # Ходы по прогнозу проигрывают - значит, прогноз ИИ кто-то угадывает: защита.
    PRED_DECAY = 0.85
    PRED_TRIGGER = 5.0

    def __init__(self, k=3, level="strong", seed=None,
                 guard=True, guard_window=20, guard_trigger=7, guard_len=20, shifts=True):
        self.k = check_k(k)
        self.level = level
        self.rng = random.Random(seed)
        if level == "strong":
            self.predictors = P.full_set(k, net_seed=0 if seed is None else int(seed) % 100000)
        elif level == "medium":
            self.predictors = P.medium_set(k)
        elif level == "novice":
            self.predictors = P.novice_set(k)
            shifts = False
            guard = False
        else:
            raise ValueError(level)
        self.shifts = list(range(k)) if shifts else [0]
        self.guard = guard
        self.guard_window = guard_window
        self.guard_trigger = guard_trigger
        self.guard_len = guard_len
        n = len(self.predictors) * len(self.shifts)
        self.decays = np.array(self.DECAYS)[:, None]
        self.scores = np.zeros((len(self.DECAYS), n))
        self.judges = np.zeros(len(self.DECAYS))
        self.plans = [None] * n            # ходы стратегий в текущем раунде (список равных)
        self.proposals = [None] * len(self.DECAYS)   # (стратегия, ходы) каждого судьи
        self.dists = [None] * len(self.predictors)
        self.results = deque(maxlen=guard_window)     # итоги ИИ: +1 победа, -1 поражение
        self.guard_left = 0
        self.strikes = 0
        self.since_strike = 0
        self.guard_triggers = 0
        self.seen = 0
        self.planned_round = -1
        self.last_choice = None
        self.last_mode = (None, -1)      # (режим, раунд) последнего choose
        self.pred_perf = 0.0             # итоги ходов «по прогнозу», с затуханием PRED_DECAY

    # --- история ---

    def _sync(self, history):
        if len(history) < self.seen:
            raise ValueError("история короче, чем ИИ уже видел: новый матч - новый ИИ")
        for r in history[self.seen:]:
            self._learn(r.human, r.ai)

    def observe(self, r):
        """Итог раунда (то же сделает и choose по истории)."""
        self._learn(r.human, r.ai)

    def _value(self, moves, h):
        if not moves:
            return 0.0
        return sum(outcome(m, h, self.k) for m in moves) / len(moves)

    def _learn(self, h, a):
        if self.planned_round != self.seen:
            self._plan()
        vals = np.array([self._value(m, h) for m in self.plans])
        self.scores *= self.decays
        self.scores += vals
        for d, prop in enumerate(self.proposals):
            self.judges[d] = self.judges[d] * self.JUDGE_DECAY + (self._value(prop[1], h) if prop else 0.0)
        for p in self.predictors:
            p.update(h, a)
        res = outcome(a, h, self.k)
        self.results.append(res)
        if self.last_mode == ("predict", self.seen):
            self.pred_perf = self.pred_perf * self.PRED_DECAY + res
        self.seen += 1
        self.since_strike += 1
        if self.guard_left > 0:
            self.guard_left -= 1
            if self.guard_left == 0:
                self.results.clear()
        elif self.guard and (self.pred_perf <= -self.PRED_TRIGGER or (
                len(self.results) >= self.guard_window // 2 and -sum(self.results) >= self.guard_trigger)):
            self.pred_perf = 0.0
            if self.since_strike > 150:
                self.strikes = 0
            self.guard_left = self.guard_len * 2 ** min(self.strikes, 5)
            self.strikes += 1
            self.since_strike = 0
            self.guard_triggers += 1

    def _plan(self):
        """Прогноз каждого предсказателя, ход каждой стратегии и выбор каждого судьи."""
        ns = len(self.shifts)
        for pi, p in enumerate(self.predictors):
            d = p.predict()
            self.dists[pi] = d
            for si, j in enumerate(self.shifts):
                if d is None:
                    self.plans[pi * ns + si] = None
                else:
                    q = [d[(b - j) % self.k] for b in range(self.k)]
                    self.plans[pi * ns + si] = best_responses(q, self.k)
        valid = np.array([pl is not None for pl in self.plans])
        for di in range(len(self.DECAYS)):
            self.proposals[di] = None
            if valid.any():
                row = np.where(valid, self.scores[di], -np.inf)
                best = int(row.argmax())
                if row[best] > 0:
                    self.proposals[di] = (best, self.plans[best])
        self.planned_round = self.seen

    # --- ход ---

    def confidence(self, judge):
        if self.proposals[judge] is None:
            return 0.0
        v = (self.judges[judge] - self.SURE_LO) / (self.SURE_HI - self.SURE_LO)
        return float(min(1.0, max(0.0, v)))

    def choose(self, history):
        """(ход, мысли). Мысли - для окна: прогноз, лидер, почему."""
        self._sync(history)
        if self.planned_round != self.seen:
            self._plan()
        ns = len(self.shifts)
        judge = int(self.judges.argmax())
        prop = self.proposals[judge]
        row = self.scores[judge]
        ranking = sorted((i for i, pl in enumerate(self.plans) if pl), key=lambda i: -row[i])
        thoughts = {"round": self.seen, "ranking": [], "mode": "random", "leader": None,
                    "dist": [1.0 / self.k] * self.k, "score": 0.0, "shift": 0,
                    "memory": round(1 / (1 - self.DECAYS[judge]))}
        for i in ranking[:5]:
            pi, si = divmod(i, ns)
            key, params = self.predictors[pi].why()
            thoughts["ranking"].append({"key": key, "params": params, "shift": self.shifts[si],
                                        "score": round(float(row[i]), 2)})
        if self.guard_left > 0:
            move = self.rng.randrange(self.k)
            thoughts["mode"] = "guard"
            thoughts["guard_left"] = self.guard_left
        elif prop is None or self.rng.random() >= self.confidence(judge):
            move = self.rng.randrange(self.k)
            thoughts["mode"] = "random"
            thoughts["confidence"] = round(self.confidence(judge), 2)
        else:
            best, moves = prop
            pi, si = divmod(best, ns)
            j = self.shifts[si]
            d = self.dists[pi]
            move = self.rng.choice(moves)
            key, params = self.predictors[pi].why()
            thoughts.update(mode="predict", leader={"key": key, "params": params}, shift=j,
                            score=round(float(row[best]), 2), confidence=round(self.confidence(judge), 2),
                            dist=[d[(b - j) % self.k] for b in range(self.k)])
        self.last_choice = move
        self.last_mode = (thoughts["mode"], self.seen)
        return move, thoughts


class RandomPlayer:
    """Честная случайность: для проверок и как нижняя планка."""

    def __init__(self, k=3, seed=None):
        self.k = k
        self.rng = random.Random(seed)

    def choose(self, history):
        return self.rng.randrange(self.k), {"mode": "random"}

    def observe(self, r):
        pass


def make_ai(level, k=3, seed=None):
    if level == "random":
        return RandomPlayer(k, seed)
    return AiPlayer(k, level, seed)


__all__ = ["AiPlayer", "RandomPlayer", "make_ai", "LEVELS", "WIN", "LOSS"]
