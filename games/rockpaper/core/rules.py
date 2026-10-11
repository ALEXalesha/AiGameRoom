"""Правила: камень-ножницы-бумага (3 знака) и камень-ножницы-бумага-ящерица-Спок (5).

Ходы - числа 0..k-1. Порядок выбран так, что одно правило годится для обоих вариантов:
ход a бьёт ход b, если (a - b) mod k нечётно.

    k = 3: 0 камень, 1 бумага, 2 ножницы
    k = 5: 0 камень, 1 бумага, 2 ножницы, 3 Спок, 4 ящерица

Проверка для k = 5: бумага бьёт камень и Спока, ножницы - бумагу и ящерицу, камень -
ножницы и ящерицу, Спок - ножницы и камень, ящерица - Спока и бумагу. Каждый знак бьёт
ровно (k - 1) / 2 других.
"""

ROCK, PAPER, SCISSORS, SPOCK, LIZARD = range(5)
NAMES = ("rock", "paper", "scissors", "spock", "lizard")
VARIANTS = (3, 5)

WIN, TIE, LOSS = 1, 0, -1


def check_k(k):
    if k not in VARIANTS:
        raise ValueError(f"вариант на {k} знаков не поддерживается")
    return k


def beats(a, b, k=3):
    """a бьёт b."""
    return (a - b) % k % 2 == 1


def outcome(a, b, k=3):
    """Итог для того, кто сыграл a: WIN, TIE или LOSS."""
    if a == b:
        return TIE
    return WIN if beats(a, b, k) else LOSS


def beaters(m, k=3):
    """Ходы, которые бьют m (по возрастанию)."""
    return [a for a in range(k) if beats(a, m, k)]


def payoff_matrix(k=3):
    """P[a][b] - итог хода a против хода b."""
    return [[outcome(a, b, k) for b in range(k)] for a in range(k)]


def expected(dist, k=3):
    """Средний итог каждого своего хода против распределения ходов соперника."""
    return [sum(dist[b] * outcome(a, b, k) for b in range(k)) for a in range(k)]


def best_responses(dist, k=3, eps=1e-9):
    """Свои ходы с лучшим средним итогом против dist (все равные - списком)."""
    ev = expected(dist, k)
    top = max(ev)
    return [a for a in range(k) if ev[a] >= top - eps]


def name(m):
    return NAMES[m]
