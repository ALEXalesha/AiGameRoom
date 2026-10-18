"""Обучение сети-дизайнера на раскладках кода.

    python -m game.train.design_train               # полное обучение, запись в game/models/
    python -m game.train.design_train --sizes 20 --steps 500   # короткий прогон

Учитель - настоящие экраны игры в Qt offscreen с раскладками кода: для каждого языка и пяти
уровней шрифта (шум z2) - сотни размеров окна со случайными ручками полей и промежутков (z0, z1)
и случайной видимостью «Выхода» и сообщения в меню. Снимок - game/design/layout.capture, стиль -
knobs.code_style (обе темы: геометрия у них одна). Отложенные образцы проверяются законами на
тех же настоящих виджетах. Паспорт designer.json: кривая, итог (средняя и худшая ошибка в px,
доля отложенных раскладок, прошедших законы).
"""
import argparse
import json
import os
import tempfile
import time

os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")      # см. paint_train.py

import numpy as np  # noqa: E402

from aikit import offscreen  # noqa: E402
from aikit.nn.optim import Adam  # noqa: E402
from games.snake.design import layout as L  # noqa: E402
from games.snake.design.designer_net import (LANGS, MAX_SLOTS, SLOTS, THEMES, DesignerNet, inputs,  # noqa: E402
                                      rects_from, size_index, target)
from games.snake.design.knobs import FONT_LEVELS, Z_DIM, code_style, knobs, style_vector  # noqa: E402
from games.snake.design.laws import check_layout  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = os.path.join(ROOT, "models")
SAMPLE_MESSAGE = ("Нет файла сети-мира models/world.npz: C:\\SnakeAi\\game\\models\\world.npz\n"
                  "Сначала обучите сеть (папка train).")


class Teacher:
    """Окно игры в offscreen с раскладкой кода; ставит состояние и снимает раскладку."""

    def __init__(self):
        offscreen.setup()
        from PySide6.QtWidgets import QApplication

        from aikit.host import Context
        from games.snake.ai.models import Models
        from games.snake.ui.sound import Sounds
        from games.snake.ui.widget import GameWidget
        self.app = QApplication.instance() or QApplication([])
        self.ctx = Context(tempfile.mkdtemp(prefix="snakeai-design-"), "dark", "ru", 0)
        self.w = GameWidget(self.ctx, Models(), sounds=Sounds(enabled=False), design=False)
        self.w.resize(1040, 720)
        self.w.show()
        self.w.play()                        # у экрана матча - настоящие надписи
        self.w.match_screen.stop()
        self.screens = {s.NAME: s for s in self.w.screens}
        self.lang = self.font = None

    def state(self, lang, font_z, z, size, screen, flags=(0, 0)):
        from games.snake.ui import theme
        w = self.w
        if lang != self.lang:
            self.ctx.set_lang(lang)
            self.lang, self.font = lang, None
        if font_z != self.font:
            # стиль через виджет: при смене размера окна он сам ставит масштаб (game/ui/look.scale_for)
            w.style_now = {"font": knobs(np.array([0, 0, font_z, 0])).font, "radius": 10.0, "colors": {}}
            w.theme_name = "dark"
            w.restyle()
            self.font = font_z
        k = knobs(z)
        for s in w.screens:
            s.set_knobs(k)
        sc = self.screens[screen]
        if screen == "menu":
            w.menu.quit_button.setVisible(bool(flags[0]))
            w.menu.message.setText(SAMPLE_MESSAGE if flags[1] else "")
            w.menu.message.setVisible(bool(flags[1]))
        w.stack.setCurrentWidget(sc)
        if (w.width(), w.height()) != tuple(size):
            w.resize(*size)
        if sc.size() != w.stack.size():
            sc.resize(w.stack.size())
        return sc

    def capture(self, *a):
        sc = self.state(*a)
        return L.capture(sc), (sc.width(), sc.height())


def collect(teacher, rng, n_sizes):
    """Образцы: (экран, w, h, язык, видимость, z, прямоугольники)."""
    out = []
    for lang in LANGS:
        for fz in FONT_LEVELS:
            for size in L.sample_sizes(rng, n_sizes):
                z = rng.uniform(-1, 1, Z_DIM)
                z[2] = fz
                for screen in SLOTS:
                    flags = (int(rng.random() < 0.5), int(rng.random() < 0.15)) if screen == "menu" else (0, 0)
                    rects, (sw, sh) = teacher.capture(lang, fz, z, size, screen, flags)
                    out.append((screen, sw, sh, lang, flags, z, rects, size))
    return out


def tensors(samples):
    from games.snake.ui import theme
    xs, ys, ms = [], [], []
    for screen, w, h, lang, flags, z, rects, _ in samples:
        for th in THEMES:
            xs.append(inputs(screen, w, h, th, lang, flags, z))
            y, m = target(screen, rects, style_vector(code_style(theme.tokens(th), z)))
            ys.append(y)
            ms.append(m)
    return np.stack(xs), np.stack(ys), np.stack(ms)


def px_error(net, x, y, m):
    """Ошибка раскладки сети против раскладки кода с запасом ROOM, px."""
    pred = net.forward(x)
    err = np.abs(pred - y)[:, :4 * MAX_SLOTS] * 1000
    mask = m[:, :4 * MAX_SLOTS] > 0
    return float(err[mask].mean()), float(err[mask].max())


def laws_pass(net, teacher, samples):
    ok = 0
    for screen, w, h, lang, flags, z, _, size in samples:
        sc = teacher.state(lang, z[2], z, size, screen, flags)
        rects = rects_from(screen, net.forward(inputs(screen, sc.width(), sc.height(), "dark", lang, flags, z)[None])[0])
        ok += not check_layout(sc, rects)
    return ok / max(1, len(samples))


def train(n_sizes=160, steps=30000, batch=512, seed=0, out=MODELS, log=print):
    rng = np.random.default_rng(seed)
    t0 = time.time()
    teacher = Teacher()
    data = collect(teacher, rng, n_sizes)
    held = collect(teacher, np.random.default_rng(seed + 1000), max(4, n_sizes // 8))
    x, y, m = tensors(data)
    vx, vy, vm = tensors(held)
    log(f"данные: {len(x)} раскладок, отложено {len(vx)}, {time.time() - t0:.0f} с")
    net = DesignerNet(rng=rng)
    opt = Adam(net.params(), lr=2e-3)
    curve = []
    sizes = size_index()
    for step in range(1, steps + 1):
        opt.lr = float(1e-5 + 0.5 * (2e-3 - 1e-5) * (1 + np.cos(np.pi * step / steps)))
        idx = rng.integers(0, len(x), batch)
        diff = (net.forward(x[idx]) - y[idx]) * m[idx]
        # недобор ширины и высоты обрезает текст - он штрафуется в 8 раз, перебор - нет
        weight = np.ones_like(diff)
        weight[:, sizes] = np.where(diff[:, sizes] < 0, 8.0, 1.0)
        net.backward(2 * weight * diff / diff.size)
        opt.step()
        if step % 1000 == 0 or step == steps:
            mean, worst = px_error(net, vx, vy, vm)
            curve.append({"step": step, "loss": float((diff ** 2).mean()), "px": mean})
            log(f"шаг {step}: потеря {curve[-1]['loss']:.3e}, ошибка {mean:.2f} px (худшая {worst:.1f}), "
                f"{time.time() - t0:.0f} с")
    mean, worst = px_error(net, vx, vy, vm)
    final = {"px_mean": mean, "px_max": worst, "laws_pass": laws_pass(net, teacher, held)}
    os.makedirs(out, exist_ok=True)
    net.save(os.path.join(out, "designer.npz"))
    passport = {"curve": curve, "final": final, "steps": steps, "layouts": len(x),
                "seconds": round(time.time() - t0)}
    with open(os.path.join(out, "designer.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(passport, f, ensure_ascii=False, indent=1)
    log(f"итог: {final}")
    return net, passport


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sizes", type=int, default=160, help="размеров окна на язык и уровень шрифта")
    ap.add_argument("--steps", type=int, default=30000)
    ap.add_argument("--out", default=MODELS)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    train(args.sizes, args.steps, seed=args.seed, out=args.out)


if __name__ == "__main__":
    main()
