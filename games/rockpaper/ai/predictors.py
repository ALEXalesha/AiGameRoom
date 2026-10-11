"""Предсказатели: каждый угадывает следующий ход человека по истории раундов.

У всех одно устройство:
    update(h, a)  - раунд сыгран: человек h, ИИ a;
    predict()     - распределение следующего хода человека (список k чисел, сумма 1)
                    или None, если сказать нечего (контекст ещё не встречался).
    why()         - коротко, на чём основан прогноз (для «Мыслей ИИ»): (ключ, параметры).

Счётчики затухают: привычка, которой человек больше не следует, забывается.
"""
from collections import deque

from games.rockpaper.core.rules import outcome

PRIOR = 0.3          # добавка к каждому счётчику: без неё один случай давал бы 100 %


def normalize(counts):
    total = sum(counts)
    k = len(counts)
    if total <= 0:
        return [1.0 / k] * k
    return [c / total for c in counts]


def smoothed(counts, prior=PRIOR):
    return normalize([c + prior for c in counts])


class Predictor:
    key = ""

    def __init__(self, k):
        self.k = k

    def update(self, h, a):
        raise NotImplementedError

    def predict(self):
        raise NotImplementedError

    def why(self):
        return self.key, {}

    @property
    def label(self):
        return self.key


class Frequency(Predictor):
    """Частоты ходов человека: за всё время (window=None) или за последние window раундов."""

    def __init__(self, k, window=None):
        super().__init__(k)
        self.window = window
        self.counts = [0.0] * k
        self.recent = deque(maxlen=window) if window else None
        self.key = f"freq{window}" if window else "freq"

    def update(self, h, a):
        self.counts[h] += 1
        if self.recent is not None:
            if len(self.recent) == self.window:
                self.counts[self.recent[0]] -= 1
            self.recent.append(h)

    def predict(self):
        if sum(self.counts) <= 0:
            return None
        return smoothed(self.counts)

    def why(self):
        return self.key, {"n": self.window or 0}


class Markov(Predictor):
    """Цепь Маркова порядка order: что человек делал после такого же «хвоста» истории.
    source: 'h' - последние ходы человека, 'a' - ходы ИИ, 'ha' - пары (человек, ИИ)."""

    def __init__(self, k, order, source="h", decay=0.92):
        super().__init__(k)
        self.order = order
        self.source = source
        self.decay = decay
        self.tail = deque(maxlen=order)
        self.table = {}
        self.key = f"markov_{source}{order}"

    def _item(self, h, a):
        return h if self.source == "h" else a if self.source == "a" else (h, a)

    def update(self, h, a):
        if len(self.tail) == self.order:
            ctx = tuple(self.tail)
            row = self.table.get(ctx)
            if row is None:
                row = self.table[ctx] = [0.0] * self.k
            for i in range(self.k):
                row[i] *= self.decay
            row[h] += 1
        self.tail.append(self._item(h, a))

    def predict(self):
        if len(self.tail) < self.order:
            return None
        row = self.table.get(tuple(self.tail))
        if row is None:
            return None
        return smoothed(row)

    def why(self):
        return "markov_" + self.source, {"n": self.order}


class Reaction(Predictor):
    """Реакция на исход: куда человек сдвигает ход после победы, ничьей, поражения.
    ref='self' - сдвиг от своего прошлого хода («выиграл - остался, проиграл - сменил»),
    ref='ai' - от прошлого хода ИИ («после проигрыша беру то, что побило бы его ход»)."""

    def __init__(self, k, ref="self", decay=0.95):
        super().__init__(k)
        self.ref = ref
        self.decay = decay
        self.table = {r: [0.0] * k for r in (-1, 0, 1)}
        self.last = None            # (h, a)
        self.key = f"react_{ref}"

    def _base(self, h, a):
        return h if self.ref == "self" else a

    def update(self, h, a):
        if self.last is not None:
            ph, pa = self.last
            res = outcome(ph, pa, self.k)
            row = self.table[res]
            for i in range(self.k):
                row[i] *= self.decay
            row[(h - self._base(ph, pa)) % self.k] += 1
        self.last = (h, a)

    def predict(self):
        if self.last is None:
            return None
        ph, pa = self.last
        row = self.table[outcome(ph, pa, self.k)]
        if sum(row) <= 0:
            return None
        shift = smoothed(row)
        base = self._base(ph, pa)
        out = [0.0] * self.k
        for s, p in enumerate(shift):
            out[(base + s) % self.k] = p
        return out

    def why(self):
        if self.last is None:
            return self.key, {}
        ph, pa = self.last
        return self.key, {"after": outcome(ph, pa, self.k)}


class HistoryMatch(Predictor):
    """Поиск по истории, как в боте Iocaine Powder: самый длинный кусок истории, который
    совпадает с её концом, и ход человека, что шёл за ним в прошлый раз.
    Индекс {хвост длины L: где он кончался в последний раз} пополняется на каждом раунде -
    поиск стоит O(max_len), а не O(длина истории)."""

    def __init__(self, k, source="ha", max_len=12, sure=0.8):
        super().__init__(k)
        self.source = source
        self.max_len = max_len
        self.sure = sure
        self.seq = []
        self.humans = []
        self.index = {}
        self.found = 0
        self.key = f"match_{source}"

    def _item(self, h, a):
        return h if self.source == "h" else a if self.source == "a" else (h, a)

    def update(self, h, a):
        n = len(self.seq)
        for L in range(1, min(self.max_len, n) + 1):
            self.index[tuple(self.seq[n - L:n])] = n
        self.seq.append(self._item(h, a))
        self.humans.append(h)

    def predict(self):
        n = len(self.seq)
        for L in range(min(self.max_len, n), 0, -1):
            j = self.index.get(tuple(self.seq[n - L:n]))
            if j is not None:
                self.found = L
                out = [(1 - self.sure) / (self.k - 1)] * self.k
                out[self.humans[j]] = self.sure
                return out
        self.found = 0
        return None

    def why(self):
        return "match_" + self.source, {"n": self.found}


def full_set(k, net_seed=0):
    """Все предсказатели сильного уровня."""
    from games.rockpaper.ai.net import OnlineNet
    ps = [Frequency(k), Frequency(k, 10), Frequency(k, 30)]
    ps += [Markov(k, n, "h") for n in (1, 2, 3, 4, 5)]
    ps += [Markov(k, n, "a") for n in (1, 2, 3)]
    ps += [Markov(k, n, "ha") for n in (1, 2, 3)]
    ps += [Reaction(k, "self"), Reaction(k, "ai")]
    ps += [HistoryMatch(k, "h"), HistoryMatch(k, "a"), HistoryMatch(k, "ha")]
    ps += [OnlineNet(k, seed=net_seed)]
    return ps


def medium_set(k):
    return [Frequency(k), Frequency(k, 10)] + [Markov(k, n, "h") for n in (1, 2, 3)]


def novice_set(k):
    return [Frequency(k), Frequency(k, 10)]
