"""Разбор после матча: какие привычки человека заметны в его ходах.

Каждая привычка - доля случаев, когда человек сделал «привычное», против доли у честно
случайного игрока (base). В разбор идут только те, где случаев не меньше MIN_CASES и
отличие от случайного заметно: z = (доля - base) / sqrt(base (1 - base) / n) не меньше Z_MIN.
"""
import math

from games.rockpaper.core.rules import LOSS, WIN, beats

MIN_CASES = 6
Z_MIN = 2.0


def _habit(key, hits, n, base, **extra):
    if n < MIN_CASES:
        return None
    rate = hits / n
    z = (rate - base) / math.sqrt(base * (1 - base) / n)
    return {"key": key, "rate": round(rate, 3), "base": round(base, 3), "n": n, "z": round(z, 2), **extra}


def analyse(rounds, k=3):
    """Список привычек по убыванию заметности."""
    out = []
    hs = [r.human for r in rounds]
    n = len(hs)
    if n:
        fav = max(range(k), key=lambda m: (hs.count(m), -m))
        out.append(_habit("favorite", hs.count(fav), n, 1 / k, move=fav))
    pairs = list(zip(rounds, rounds[1:]))
    out.append(_habit("repeat", sum(b.human == a.human for a, b in pairs), len(pairs), 1 / k))
    out.append(_habit("cycle_up", sum(b.human == (a.human + 1) % k for a, b in pairs), len(pairs), 1 / k))
    out.append(_habit("cycle_down", sum(b.human == (a.human - 1) % k for a, b in pairs), len(pairs), 1 / k))
    out.append(_habit("copy_ai", sum(b.human == a.ai for a, b in pairs), len(pairs), 1 / k))
    half = (k - 1) / 2 / k
    lost = [(a, b) for a, b in pairs if a.result == LOSS]
    out.append(_habit("loss_beat_ai", sum(beats(b.human, a.ai, k) for a, b in lost), len(lost), half))
    out.append(_habit("loss_shift", sum(b.human != a.human for a, b in lost), len(lost), (k - 1) / k))
    won = [(a, b) for a, b in pairs if a.result == WIN]
    out.append(_habit("win_stay", sum(b.human == a.human for a, b in won), len(won), 1 / k))
    triples = [(a, b, c) for a, b, c in zip(rounds, rounds[1:], rounds[2:]) if a.human == b.human]
    out.append(_habit("avoid_triple", sum(c.human != b.human for a, b, c in triples), len(triples),
                      (k - 1) / k))
    found = [h for h in out if h is not None and h["z"] >= Z_MIN]
    return sorted(found, key=lambda h: -h["z"])


def caught_at(rounds, start=10):
    """Раунд, начиная с которого ИИ по счёту впереди до конца матча, или None."""
    lead = 0
    at = None
    for i, r in enumerate(rounds, 1):
        lead += (r.result == LOSS) - (r.result == WIN)
        if lead > 0:
            if at is None and i >= start:
                at = i
        else:
            at = None
    return at
