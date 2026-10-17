"""Обучение сети-мира на примерах учителя.

    python -m game.train.world_train                 # полное обучение, запись в game/models/
    python -m game.train.world_train --steps 300     # короткий прогон для проверки

Учится на маленьких полях (правила от размера не зависят, а свёртка на поле 12x12 в семь
раз дешевле, чем на 32x32), с долей полей 32x32 - на них же и проверяется точность.
"""
import argparse
import json
import os
import time

import numpy as np

from aikit.nn import losses
from aikit.nn.optim import Adam
from games.snake.teacher.data import play, tensors
from games.snake.core.cells import EMPTY
from games.snake.ai.world_net import WorldNet

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
SIZES = (8, 10, 12, 16)
FOOD_WEIGHT = 0.3


def make_pool(rng, size, n):
    return tensors(play(rng, size, size, n))


def batch_loss(net, t, idx):
    x, moved, weight, events, ev_w, food, food_mask = (a[idx] for a in t)
    cells, food_logits, ev_logits = net.forward(x)
    B = len(idx)
    l_cells, d_cells = losses.softmax_xent(cells, moved, weight)
    l_ev, d_ev = losses.bce(ev_logits, events, ev_w)
    l_food, d_food = losses.softmax_xent(food_logits.reshape(B, -1), food, food_mask)
    d_food = FOOD_WEIGHT * d_food.reshape(food_logits.shape)
    return l_cells + l_ev + FOOD_WEIGHT * l_food, (d_cells, d_food, d_ev)


def evaluate(net, t, chunk=64):
    """Точность на готовых тензорах: доля ходов, где поле совпало целиком (ходы без
    столкновений), где совпали все события, и средняя вероятность еды на занятых клетках."""
    x, moved, weight, events, ev_w, food, food_mask = t
    field_ok = field_n = ev_ok = 0
    food_bad = []
    for i in range(0, len(x), chunk):
        sl = slice(i, i + chunk)
        cells, food_logits, ev_logits = net.forward(x[sl])
        crash = events[sl, 2:].max(axis=1) > 0
        same = (cells.argmax(axis=-1) == moved[sl]).all(axis=(1, 2))
        field_ok += int(same[~crash].sum())
        field_n += int((~crash).sum())
        pred = losses.sigmoid(ev_logits) > 0.5
        ev_ok += int(((pred == (events[sl] > 0.5)) | (ev_w[sl] == 0)).all(axis=1).sum())
        B = cells.shape[0]
        probs = losses.softmax(food_logits.reshape(B, -1).astype(np.float64))
        occupied = (moved[sl].reshape(B, -1) != EMPTY)
        for b in np.nonzero(food_mask[sl] > 0)[0]:
            food_bad.append(float(probs[b][occupied[b]].sum()))
    return {
        "field": field_ok / max(field_n, 1),
        "events": ev_ok / len(x),
        "food_on_occupied": float(np.mean(food_bad)) if food_bad else 0.0,
    }


def evaluate_symmetric(net, samples):
    """Доля ходов без столкновения, где поле совпало целиком, - так, как сеть ходит в игре:
    с усреднением по восьми видам поля (WorldNet.predict)."""
    ok = n = 0
    for s in samples:
        if s.events[2:].max() > 0:
            continue
        n += 1
        ok += bool(np.array_equal(net.predict(s.field, s.a0, s.a1)[0], s.moved))
    return ok / max(n, 1)


def train(steps=20000, batch=32, seed=0, pool=12000, big_pool=3000, lr=2e-3,
          eval_every=500, log=print, hidden=48, init=None):
    rng = np.random.default_rng(seed)
    t0 = time.time()
    pools = {s: make_pool(rng, s, pool) for s in SIZES}
    pools[32] = make_pool(rng, 32, big_pool)
    held = make_pool(np.random.default_rng(seed + 1000), 32, 2000)
    log(f"данные готовы за {time.time() - t0:.0f} с")

    net = WorldNet.load(init) if init else WorldNet(hidden=hidden, rng=rng)
    opt = Adam(net.params(), lr=lr)
    curve = []
    sizes = list(pools)
    probs = np.array([1, 1, 1, 1, 0.5])
    probs = probs / probs.sum()
    run = 0.0
    for it in range(1, steps + 1):
        # в последней четверти - плавное снижение шага
        opt.lr = lr * (1.0 if it < steps * 0.75 else max(0.05, (steps - it) / (steps * 0.25)))
        t = pools[sizes[rng.choice(len(sizes), p=probs)]]
        idx = rng.integers(0, len(t[0]), batch)
        loss, grads = batch_loss(net, t, idx)
        net.backward(*grads)
        opt.step()
        run = loss if it == 1 else 0.98 * run + 0.02 * loss
        if it % eval_every == 0 or it == steps:
            acc = evaluate(net, held)
            curve.append({"step": it, "loss": round(run, 5), **{k: round(v, 5) for k, v in acc.items()}})
            log(f"{it:6d}  потеря {run:.4f}  поле {acc['field']:.4f}  события {acc['events']:.4f}"
                f"  еда на занятых {acc['food_on_occupied']:.4f}  {time.time() - t0:.0f} с")
    return net, curve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--hidden", type=int, default=48)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--init", help="дообучать с этих весов (.npz), а не с нуля")
    ap.add_argument("--out", default=os.path.join(MODELS, "world"))
    args = ap.parse_args()
    net, curve = train(args.steps, seed=args.seed, hidden=args.hidden, lr=args.lr, init=args.init)
    steps_before = 0
    if args.init and os.path.exists(os.path.splitext(args.init)[0] + ".json"):
        # кривая дообучения продолжает прежнюю - в статистике видно всё обучение целиком
        with open(os.path.splitext(args.init)[0] + ".json", encoding="utf-8") as f:
            before = json.load(f)
        steps_before = before["curve"][-1]["step"]
        curve = before["curve"] + [{**c, "step": c["step"] + steps_before} for c in curve]
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    net.save(args.out + ".npz")
    with open(args.out + ".json", "w", encoding="utf-8") as f:
        final = {**curve[-1], "field_symmetric": round(evaluate_symmetric(net, play(np.random.default_rng(args.seed + 1000), 32, 32, 2000)), 5)}
        json.dump({"steps": steps_before + args.steps, "seed": args.seed, "init": bool(args.init), "lr": args.lr,
                   "final": final, "curve": curve},
                  f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
