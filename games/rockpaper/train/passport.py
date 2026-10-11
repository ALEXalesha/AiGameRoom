"""Паспорт ИИ: проверки силы против ботов с привычками, против честной случайности и против
тех, кто сам пытается предсказать ИИ.

    python -m game.train.passport [--matches 40] [--rounds 100] [--processes 4]

Пишет game/models/rockpaper-passport.json. Каждый матч считается с зерном
arena.match_seed(seed, i): тесты пересчитывают первые матчи и сверяют раунд в раунд.
Сеть заранее не обучается - она учится по ходу каждого матча, поэтому «обучения» в
паспорте нет, есть время расчёта.
"""
import argparse
import json
import math
import os
import platform
import time

from aikit.trainlog import limit_threads

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "game", "models", "rockpaper-passport.json")
SAMPLE = 2

LEVEL_BOTS = {
    "strong": ("repeat", "cycle", "wsls", "markov2", "biased", "human", "random", "mirror", "exploit"),
    "medium": ("repeat", "cycle", "wsls", "markov2", "biased", "human", "random", "mirror"),
    "novice": ("repeat", "cycle", "wsls", "markov2", "biased", "human", "random", "mirror"),
}


def checks():
    """(k, уровень, бот, зерно) - зерно своё у каждой проверки."""
    out = []
    for k in (3, 5):
        for level, bots in LEVEL_BOTS.items():
            for b, bot in enumerate(bots):
                out.append((k, level, bot, 1000 * k + 100 * ("strong", "medium", "novice").index(level) + b))
    return out


def _one(job):
    k, level, bot, seed, matches, rounds = job
    from games.rockpaper.ai.arena import run, summary
    t0 = time.time()
    lines = run(level, bot, matches, rounds, seed, k)
    s = summary(lines)
    return {"k": k, "level": level, "bot": bot, "seed": seed, "matches": matches, "rounds": rounds,
            **s, "seconds": round(time.time() - t0, 1), "sample": lines[:SAMPLE]}


def hindsight_edge(moves, k, order):
    """Сколько выиграл бы человек за раунд, если бы заранее знал всю таблицу «после таких
    order ходов ИИ его следующий ход распределён так» и всегда бил лучшее. Для честно
    случайного ИИ - около нуля (немного больше нуля из-за конечной выборки)."""
    from collections import defaultdict
    from games.rockpaper.core.rules import expected
    table = defaultdict(lambda: [0] * k)
    for i in range(order, len(moves)):
        table[tuple(moves[i - order:i])][moves[i]] += 1
    total = sum(sum(c) for c in table.values())
    gain = 0.0
    for c in table.values():
        n = sum(c)
        gain += max(expected([x / n for x in c], k)) * n
    return gain / max(total, 1)


def fairness(k, rounds=4000, seeds=(1, 2, 3, 4, 5)):
    """Против случайного: доли раундов, равномерность ходов ИИ (хи-квадрат) и выигрыш
    человека, знающего задним числом таблицы ходов ИИ порядка 0-2. Несколько матчей с
    разными зёрнами вместе - так одно неудачное зерно не решает."""
    from games.rockpaper.ai.arena import ai_results, play
    from games.rockpaper.ai.bots import make_bot
    from games.rockpaper.ai.player import make_ai
    res, moves_all, triggers, edges = "", [], 0, {0: 0.0, 1: 0.0, 2: 0.0}
    for seed in seeds:
        ai = make_ai("strong", k, seed=7000 + seed)
        m = play(ai, make_bot("random", k, seed=8000 + seed), rounds, k)
        res += ai_results(m)
        mv = [r.ai for r in m.rounds]
        moves_all += mv
        triggers += ai.guard_triggers
        for o in edges:
            edges[o] += hindsight_edge(mv, k, o) / len(seeds)
    n = len(res)
    cnt = [moves_all.count(i) for i in range(k)]
    chi = sum((c - n / k) ** 2 / (n / k) for c in cnt)
    # тот же расчёт для честного генератора той же длины - с чем сравнивать
    import random
    rr = random.Random(99)
    base = {o: sum(hindsight_edge([rr.randrange(k) for _ in range(rounds)], k, o)
                   for _ in seeds) / len(seeds) for o in edges}
    return {"k": k, "rounds": n, "matches": len(seeds),
            "win": round(res.count("W") / n, 4), "tie": round(res.count("T") / n, 4),
            "loss": round(res.count("L") / n, 4),
            "ai_moves": cnt, "chi2_moves": round(chi, 2), "p_moves": round(chi2_sf(chi, k - 1), 4),
            "hindsight_edge": {str(o): round(v, 4) for o, v in edges.items()},
            "hindsight_edge_true_random": {str(o): round(v, 4) for o, v in base.items()},
            "guard_triggers": triggers}


def chi2_sf(x, df):
    """P(хи-квадрат с df степенями > x): регуляризованная неполная гамма, ряд и цепная дробь."""
    a, x = df / 2.0, x / 2.0
    if x <= 0:
        return 1.0
    if x < a + 1:
        term = total = 1.0 / a
        n = a
        for _ in range(500):
            n += 1
            term *= x / n
            total += term
            if term < total * 1e-12:
                break
        return max(0.0, 1.0 - total * math.exp(-x + a * math.log(x) - math.lgamma(a)))
    b = x + 1 - a
    c = 1e300
    d = 1 / b
    h = d
    for i in range(1, 500):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1 / d if abs(d) > 1e-300 else 1e300
        c = b + an / c if abs(c) > 1e-300 else 1e-300 + b
        h *= d * c
        if abs(d * c - 1) < 1e-12:
            break
    return min(1.0, math.exp(-x + a * math.log(x) - math.lgamma(a)) * h)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Паспорт ИИ RockPaperAi")
    ap.add_argument("--matches", type=int, default=40)
    ap.add_argument("--rounds", type=int, default=100)
    ap.add_argument("--processes", type=int, default=4)
    ap.add_argument("--out", default=PATH)
    args = ap.parse_args(argv)
    limit_threads(1, force=True)
    from games.rockpaper.ai.net import OnlineNet
    from games.rockpaper.version import VERSION
    t0 = time.time()
    jobs = [(k, lv, b, s, args.matches, args.rounds) for k, lv, b, s in checks()]
    if args.processes > 1:
        import multiprocessing as mp
        with mp.get_context("spawn").Pool(args.processes) as pool:
            results = pool.map(_one, jobs)
    else:
        results = [_one(j) for j in jobs]
    for r in results:
        a = r["after30"]
        print(f"k={r['k']} {r['level']:7} {r['bot']:8} побед ИИ {r['all']['win']:.3f} "
              f"(после 30-го {a['win']:.3f}, поражений {a['loss']:.3f})", flush=True)
    fair = [fairness(3), fairness(5)]
    passport = {
        "version": VERSION,
        "matches_per_check": args.matches,
        "rounds_per_match": args.rounds,
        "checks": results,
        "fairness": fair,
        "network": {"parameters": {str(k): OnlineNet(k).parameters() for k in (3, 5)},
                    "training": "по ходу матча, заранее не обучается"},
        "seconds": round(time.time() - t0, 1),
        "processes": args.processes,
        "python": platform.python_version(),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(passport, f, ensure_ascii=False, indent=1)
    print(f"паспорт: {args.out}, {passport['seconds']} с")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
