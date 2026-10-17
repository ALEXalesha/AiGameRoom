"""Обучение сети-художника на тайлах кодового художника.

    python -m game.train.paint_train                # полное обучение, запись в game/models/
    python -m game.train.paint_train --steps 300    # короткий прогон для проверки

Данные: все ключи целых змеек (game/design/tiles.common_keys) x 3 палитры x шумы «руки».
Отложенные шумы - для проверки законов (game/design/laws.check_tiles). Паспорт painter.json:
кривая обучения, итог (среднее и худшее отличие тайла от кодового, доля наборов, прошедших
законы) и порог закона limit, по которому игра проверяет тайлы.
"""
import argparse
import json
import os
import time

# OpenBLAS по умолчанию берёт все 16 потоков, и рядом с другими процессами умножение матриц
# этой сети шло в 25 раз медленнее, чем на 4 потоках (замер 17.10: 75 мс против 3 мс)
os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")

import numpy as np  # noqa: E402

from aikit import offscreen  # noqa: E402
from aikit.nn.optim import Adam  # noqa: E402
from games.snake.design.knobs import Z_DIM  # noqa: E402
from games.snake.design.laws import check_tiles  # noqa: E402
from games.snake.design.painter_net import PainterNet  # noqa: E402
from games.snake.design.tiles import common_keys, code_tiles, features, group  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
PALETTES = 3
LIMIT = 0.04         # закон: среднее |разность| тайла сети и кода, доля от 255 (худший тайл
                     # обученной сети 17.10 - 0.023, тайл из нулей - больше 0.1)


def make_data(rng, n_z, extremes=False):
    """(x, y, sets): входы, тайлы кода (uint8, плоско) и наборы (палитра, шум, ключи) для законов."""
    keys = common_keys()
    zs = [rng.uniform(-1, 1, Z_DIM) for _ in range(n_z)]
    if extremes:
        zs += [np.zeros(Z_DIM), np.ones(Z_DIM), -np.ones(Z_DIM)]
    xs, ys, sets = [], [], []
    for pal in range(PALETTES):
        for z in zs:
            tiles = code_tiles(keys, pal, z)
            xs.append(features(keys, pal, z))
            ys.append(tiles.reshape(len(keys), -1))
            sets.append((pal, z, tiles))
    return np.concatenate(xs), np.concatenate(ys), sets


def evaluate(net, sets, limit=LIMIT):
    keys = common_keys()
    kinds = [group(k) for k in keys]
    diffs, passed = [], 0
    for pal, z, code in sets:
        drawn = net.draw(keys, pal, z)
        d = np.abs(drawn.astype(np.float32) - code).reshape(len(keys), -1).mean(1) / 255
        diffs.append(d)
        passed += not check_tiles(drawn, code, kinds, limit)
    diffs = np.concatenate(diffs)
    return {"diff_mean": float(diffs.mean()), "diff_max": float(diffs.max()),
            "laws_pass": passed / len(sets)}


def train(steps=24000, batch=256, seed=0, out=MODELS, log=print):
    offscreen.setup()
    from PySide6.QtGui import QGuiApplication
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 - QPainter нужен
    rng = np.random.default_rng(seed)
    t0 = time.time()
    x, y, _ = make_data(rng, 64, extremes=True)
    _, _, val = make_data(np.random.default_rng(seed + 1000), 10)
    log(f"данные: {len(x)} тайлов, {time.time() - t0:.0f} с")
    net = PainterNet(rng=rng)
    opt = Adam(net.params(), lr=1e-3)
    curve = []
    for step in range(1, steps + 1):
        opt.lr = float(1e-4 + 0.5 * (1e-3 - 1e-4) * (1 + np.cos(np.pi * step / steps)))
        idx = rng.integers(0, len(x), batch)
        target = y[idx].astype(np.float32) / 255
        pred = net.forward(x[idx])
        diff = pred - target
        net.backward(2 * diff / diff.size)
        opt.step()
        if step % 1000 == 0 or step == steps:
            m = evaluate(net, val[::3])
            curve.append({"step": step, "loss": float((diff ** 2).mean()), "diff": m["diff_mean"]})
            log(f"шаг {step}: потеря {curve[-1]['loss']:.5f}, отличие {m['diff_mean']:.4f}, "
                f"законы {m['laws_pass']:.2f}, {time.time() - t0:.0f} с")
    final = evaluate(net, val)
    os.makedirs(out, exist_ok=True)
    net.save(os.path.join(out, "painter.npz"))
    passport = {"curve": curve, "final": final, "limit": LIMIT, "steps": steps, "tiles": len(x),
                "seconds": round(time.time() - t0)}
    with open(os.path.join(out, "painter.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(passport, f, ensure_ascii=False, indent=1)
    log(f"итог: {final}")
    return net, passport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=24000)
    ap.add_argument("--out", default=MODELS)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    train(args.steps, seed=args.seed, out=args.out)


if __name__ == "__main__":
    main()
