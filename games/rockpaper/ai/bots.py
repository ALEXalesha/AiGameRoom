"""Боты с привычками - соперники ИИ в проверках силы и в режиме «ИИ против бота».

Бот играет за человека: move(history) по истории раундов, где Round.human - его ходы,
Round.ai - ходы ИИ. Случайность - только из своего генератора с зерном.
"""
import random

from games.rockpaper.ai.predictors import Frequency, Markov
from games.rockpaper.core.rules import WIN, LOSS, beaters, best_responses


class Bot:
    key = ""
    human_like = True

    def __init__(self, k=3, seed=0):
        self.k = k
        self.rng = random.Random(seed)

    def move(self, history):
        raise NotImplementedError

    def any(self):
        return self.rng.randrange(self.k)


class RandomBot(Bot):
    """Честная случайность: обыграть нельзя, проиграть тоже."""
    key = "random"
    human_like = False

    def move(self, history):
        return self.any()


class Repeater(Bot):
    """Чаще всего повторяет свой прошлый ход (stay доля), иначе - любой."""
    key = "repeat"

    def __init__(self, k=3, seed=0, stay=0.8):
        super().__init__(k, seed)
        self.stay = stay

    def move(self, history):
        if history and self.rng.random() < self.stay:
            return history[-1].human
        return self.any()


class Cycler(Bot):
    """Идёт по кругу: камень → ножницы → бумага → камень… (step=-1 на трёх знаках)."""
    key = "cycle"

    def __init__(self, k=3, seed=0, step=-1):
        super().__init__(k, seed)
        self.step = step
        self.start = self.rng.randrange(k)

    def move(self, history):
        if not history:
            return self.start
        return (history[-1].human + self.step) % self.k


class WinStayLoseShift(Bot):
    """Выиграл - остаётся; проиграл - берёт то, что побило бы прошлый ход ИИ; ничья - любой."""
    key = "wsls"

    def move(self, history):
        if not history:
            return self.any()
        r = history[-1]
        if r.result == WIN:
            return r.human
        if r.result == LOSS:
            return self.rng.choice(beaters(r.ai, self.k))
        return self.any()


class Markov2Bot(Bot):
    """Ход зависит от двух своих прошлых: у каждой пары свой любимый ход (доля fav)."""
    key = "markov2"

    def __init__(self, k=3, seed=0, fav=0.75):
        super().__init__(k, seed)
        self.fav = fav
        self.table = {(a, b): self.rng.randrange(k) for a in range(k) for b in range(k)}

    def move(self, history):
        if len(history) < 2 or self.rng.random() >= self.fav:
            return self.any()
        return self.table[(history[-2].human, history[-1].human)]


class Biased(Bot):
    """Любит один знак: камень 50 %, бумага 30 %, ножницы 20 % (на пяти - 40/25/15/10/10)."""
    key = "biased"

    def __init__(self, k=3, seed=0):
        super().__init__(k, seed)
        self.weights = [0.5, 0.3, 0.2] if k == 3 else [0.4, 0.25, 0.15, 0.1, 0.1]

    def move(self, history):
        return self.rng.choices(range(self.k), self.weights)[0]


class HumanLike(Bot):
    """Похож на человека, который старается быть случайным: не ставит три одинаковых подряд,
    после проигрыша в половине случаев берёт то, что побило бы ход ИИ, после победы в
    половине случаев остаётся, в остальном - случайно."""
    key = "human"

    def move(self, history):
        m = None
        if history:
            r = history[-1]
            if r.result == LOSS and self.rng.random() < 0.5:
                m = self.rng.choice(beaters(r.ai, self.k))
            elif r.result == WIN and self.rng.random() < 0.5:
                m = r.human
        if m is None:
            m = self.any()
        if len(history) >= 2 and history[-1].human == history[-2].human == m:
            m = self.rng.choice([x for x in range(self.k) if x != m])
        return m


class Mirror(Bot):
    """Сам предсказывает ИИ: Маркова 1 по ходам ИИ (а пока пусто - частоты) и бьёт
    предсказанное. Проверка, что ИИ не проваливается, когда угадывают его самого."""
    key = "mirror"
    human_like = False

    def __init__(self, k=3, seed=0):
        super().__init__(k, seed)
        # предсказатели ходов ИИ: подставляем ИИ на место «человека»
        self.freq = Frequency(k)
        self.markov = Markov(k, 1, "h")
        self.seen = 0

    def move(self, history):
        for r in history[self.seen:]:
            self.freq.update(r.ai, r.human)
            self.markov.update(r.ai, r.human)
        self.seen = len(history)
        d = self.markov.predict() or self.freq.predict()
        if d is None:
            return self.any()
        return self.rng.choice(best_responses(d, self.k))


class Exploiter(Bot):
    """Худший случай: держит у себя копию того же ИИ (тот же уровень, своё зерно), считает,
    что ИИ сыграет сейчас, и бьёт это. Против ИИ без случайности выигрывал бы всегда."""
    key = "exploit"
    human_like = False

    def __init__(self, k=3, seed=0, level="strong"):
        super().__init__(k, seed)
        from games.rockpaper.ai.player import AiPlayer
        self.copy = AiPlayer(k, level, seed=seed + 7919)

    def move(self, history):
        guess, _ = self.copy.choose(history)
        return self.rng.choice(beaters(guess, self.k))


BOTS = {b.key: b for b in (Repeater, Cycler, WinStayLoseShift, Markov2Bot, Biased, HumanLike,
                           RandomBot, Mirror, Exploiter)}
HABIT_BOTS = ("repeat", "cycle", "wsls", "markov2", "biased", "human")


def make_bot(key, k=3, seed=0):
    return BOTS[key](k, seed)
