"""Обучение сети-соперника: подражание боту, потом пробы и ошибки (REINFORCE).

    python -m game.train.player_train
    python -m game.train.player_train --quick      # короткий прогон для проверки

Играется в учителе (правила кодом) - он в тысячи раз быстрее сети-мира, а правила те же.
Записывает game/models/player_novice.npz, player_medium.npz, player_strong.npz и паспорт
game/models/player.json.
"""
import os

os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
os.environ.setdefault("OMP_NUM_THREADS", "4")

import argparse  # noqa: E402
import copy  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402

from aikit.nn import losses  # noqa: E402
from aikit.nn.optim import Adam  # noqa: E402
from games.snake.ai.bot import bot_move  # noqa: E402
from games.snake.ai.player_net import PlayerNet  # noqa: E402
from games.snake.ai.view import view  # noqa: E402
from games.snake.teacher.data import random_field  # noqa: E402
from games.snake.teacher.rules import step  # noqa: E402
from games.snake.core.cells import EMPTY, FOOD  # noqa: E402
from games.snake.core.start import start_field  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
SIZE = 32
MAX_STEPS = 600


def with_food(field, rng):
    if not (field == FOOD).any():
        empties = np.argwhere(field == EMPTY)
        field[tuple(empties[rng.integers(len(empties))])] = FOOD
    return field


def imitation_data(rng, n, noise=0.1):
    """Позиции из партий бот против бота (с долей случайных ходов, чтобы попадать и в
    неудобные положения); метка - ход бота из этой позиции."""
    xs, ys = [], []
    while len(xs) < n:
        field = start_field() if rng.random() < 0.5 else with_food(random_field(rng, SIZE, SIZE, 60), rng)
        for _ in range(MAX_STEPS):
            moves = []
            for s in (0, 1):
                label = bot_move(field, s)
                xs.append(view(field, s))
                ys.append(label)
                moves.append(label if rng.random() > noise else int(rng.integers(0, 4)))
            o = step(field, moves[0], moves[1], rng)
            if o.field is None:
                break
            field = o.field
    return np.stack(xs[:n]), np.array(ys[:n])


class Bot:
    def act(self, field, s, **_):
        return bot_move(field, s)


class Random:
    def __init__(self, rng):
        self.rng = rng

    def act(self, field, s, **_):
        return int(self.rng.integers(0, 4))


def play_round(net, rival, rng, greedy=True, record=None):
    """Раунд: сеть - змейка 1, rival - змейка 0. Возвращает 1 победа, -1 поражение,
    0 ничья или лимит ходов. record - список для (вход, ход, награда) при пробах и ошибках."""
    field = start_field(SIZE, SIZE)
    for _ in range(MAX_STEPS):
        x = view(field, 1)
        a = net.act(field, 1, greedy=greedy, rng=rng)
        o = step(field, rival.act(field, 0), a, rng)
        reward = 0.0
        result = None
        if o.field is None:
            c0, c1 = o.crashed
            result = 0 if c0 == c1 else (1 if c0 else -1)
            reward = {1: 1.0, -1: -1.0, 0: -0.5}[result]
        elif o.ate[1]:
            reward = 0.5
        if record is not None:
            record.append((x, a, reward))
        if result is not None:
            return result
        field = o.field
    return 0


def evaluate(net, rival, rng, rounds):
    res = [play_round(net, rival, rng) for _ in range(rounds)]
    return {"win": res.count(1) / rounds, "loss": res.count(-1) / rounds, "draw": res.count(0) / rounds}


def imitate(net, x, y, xt, yt, steps, rng, snapshot_at, log, batch=256, lr=1e-3):
    opt = Adam(net.params(), lr=lr)
    curve, snapshot = [], None
    for it in range(1, steps + 1):
        idx = rng.integers(0, len(x), batch)
        loss, d = losses.softmax_xent(net.logits(x[idx]), y[idx])
        net.backward(d)
        opt.step()
        if it == snapshot_at:
            snapshot = copy.deepcopy(net)
        if it % 250 == 0 or it == steps or it == snapshot_at:
            acc = float((net.logits(xt).argmax(axis=1) == yt).mean())
            curve.append({"step": it, "loss": round(loss, 4), "accuracy": round(acc, 4)})
            log(f"подражание {it:6d}  потеря {loss:.4f}  совпадение с ботом {acc:.4f}")
    return snapshot, curve


def reinforce(net, rng, iters, log, rounds_per_iter=8, lr=2e-5, gamma=0.97):
    """REINFORCE с базой: ходы сэмплируются из сети, после раунда каждый ход тянется к
    дисконтированной награде минус средняя."""
    opt = Adam(net.params(), lr=lr)
    bot = Bot()
    curve = []
    for it in range(1, iters + 1):
        xs, acts, rets = [], [], []
        total = 0.0
        for _ in range(rounds_per_iter):
            rec = []
            play_round(net, bot, rng, greedy=False, record=rec)
            g = 0.0
            out = []
            for x, a, r in reversed(rec):
                g = r + gamma * g
                out.append(g)
                total += r
            out.reverse()
            xs += [x for x, _, _ in rec]
            acts += [a for _, a, _ in rec]
            rets += out
        rets = np.array(rets, np.float32)
        adv = (rets - rets.mean()) / (rets.std() + 1e-6)
        x = np.stack(xs)
        p = losses.softmax(net.logits(x).astype(np.float64))
        d = p.copy()
        d[np.arange(len(acts)), acts] -= 1.0
        d *= adv[:, None] / len(acts)
        net.backward(d.astype(np.float32))
        opt.step()
        curve.append({"episode": it * rounds_per_iter, "reward": round(total / rounds_per_iter, 3)})
        if it % 20 == 0:
            log(f"пробы {it:5d}  награда за раунд {total / rounds_per_iter:.3f}")
    return curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--samples", type=int, default=150000)
    ap.add_argument("--steps", type=int, default=12000)
    ap.add_argument("--rl-iters", type=int, default=400)
    ap.add_argument("--eval-rounds", type=int, default=100)
    ap.add_argument("--out", default=MODELS)
    args = ap.parse_args()
    if args.quick:
        args.samples, args.steps, args.rl_iters, args.eval_rounds = 8000, 600, 10, 10

    rng = np.random.default_rng(args.seed)
    t0 = time.time()

    def log(msg):
        print(f"{msg}  [{time.time() - t0:.0f} с]", flush=True)

    x, y = imitation_data(rng, args.samples)
    xt, yt = imitation_data(np.random.default_rng(args.seed + 99), max(2000, args.samples // 20))
    log(f"данные: {len(x)} позиций")

    net = PlayerNet(rng=rng)
    novice, im_curve = imitate(net, x, y, xt, yt, args.steps, rng, max(1, args.steps // 25), log)
    medium = net

    bot, rand = Bot(), Random(np.random.default_rng(7))
    ev_rng = lambda: np.random.default_rng(args.seed + 500)  # noqa: E731 - одни и те же раунды
    levels = {}
    for name, n in (("novice", novice), ("medium", medium)):
        levels[name] = {"vs_bot": evaluate(n, bot, ev_rng(), args.eval_rounds),
                        "vs_random": evaluate(n, rand, ev_rng(), args.eval_rounds)}
        log(f"{name}: {levels[name]}")

    strong = copy.deepcopy(medium)
    best, best_score = copy.deepcopy(medium), levels["medium"]["vs_bot"]["win"] - levels["medium"]["vs_bot"]["loss"]
    rl_curve = []
    chunk = max(1, args.rl_iters // 8)
    for k in range(0, args.rl_iters, chunk):
        rl_curve += reinforce(strong, rng, chunk, log)
        score = evaluate(strong, bot, ev_rng(), args.eval_rounds)
        s = score["win"] - score["loss"]
        log(f"после {k + chunk} итераций проб: {score}")
        if s >= best_score:
            best, best_score = copy.deepcopy(strong), s
    levels["strong"] = {"vs_bot": evaluate(best, bot, ev_rng(), args.eval_rounds),
                        "vs_random": evaluate(best, rand, ev_rng(), args.eval_rounds)}
    log(f"strong: {levels['strong']}")

    os.makedirs(args.out, exist_ok=True)
    for name, n in (("novice", novice), ("medium", medium), ("strong", best)):
        n.save(os.path.join(args.out, f"player_{name}.npz"))
    passport = {"seed": args.seed, "samples": len(x), "imitation_steps": args.steps,
                "rl_iters": args.rl_iters, "eval_rounds": args.eval_rounds,
                "levels": levels, "imitation_curve": im_curve, "rl_curve": rl_curve}
    with open(os.path.join(args.out, "player.json"), "w", encoding="utf-8") as f:
        json.dump(passport, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
