"""Законы проверки ответа сетей-оформителей. Пустой список - законы прошли.

Раскладка: всё внутри окна и своего родителя, соседи не налезают, каждый элемент не меньше,
чем нужно его содержимому (minimumSizeHint, у переносимого текста - heightForWidth), кнопки
не ниже 28 px, видимые элементы все на месте. Стиль: текст читается (контраст WCAG).
Поле: в тайлах сети узнаётся тот же вид клетки, что у кода, и тайл близок к кодовому.
"""
import numpy as np
from PySide6.QtWidgets import QPushButton

from games.snake.design.knobs import contrast

SIZE_SLACK = 0          # px: недобор размера до потребности содержимого (1 px уже резал
                        # нижнюю строку подсказки при шрифте +10%: закон test_text_fits)
MAX_SLACK = 6           # px: лишнее сверх предела виджета Qt срезает сам, элемент лишь сдвинут
MIN_BUTTON_H = 28


def _inside(inner, outer):
    x, y, w, h = inner
    ox, oy, ow, oh = outer
    return x >= ox and y >= oy and x + w <= ox + ow and y + h <= oy + oh


def _overlap(a, b):
    w = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    h = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return w > 0 and h > 0


def need(widget, w):
    """Сколько места нужно содержимому виджета при ширине w: (ширина, высота)."""
    msh = widget.minimumSizeHint()
    mn = widget.minimumSize()
    nw = max(msh.width(), mn.width())
    nh = max(msh.height(), mn.height())
    if widget.hasHeightForWidth():
        lay = widget.layout()
        # у контейнера heightForWidth - желаемая высота, а нужна наименьшая
        hfw = lay.totalMinimumHeightForWidth(int(w)) if lay is not None else widget.heightForWidth(int(w))
        nh = max(hfw, mn.height())
    return nw, nh


def check_layout(screen, rects):
    """Законы раскладки экрана screen (виджеты настоящие) для прямоугольников rects."""
    bad = []
    window = (0, 0, screen.width(), screen.height())
    elements = screen.elements()
    for name, widget, parent in elements:
        if widget.isHidden():
            continue
        r = rects.get(name)
        if r is None:
            bad.append(f"{name}: нет места")
            continue
        x, y, w, h = r
        if w <= 0 or h <= 0:
            bad.append(f"{name}: пустой {r}")
            continue
        box = window if parent is None else rects.get(parent, window)
        if not _inside(r, box):
            bad.append(f"{name}: вне {'окна' if parent is None else parent} {r}")
        nw, nh = need(widget, w)
        if w < nw - SIZE_SLACK or h < nh - SIZE_SLACK:
            bad.append(f"{name}: мало места {w}x{h}, нужно {nw}x{nh}")
        mx = widget.maximumSize()
        if w > mx.width() + MAX_SLACK or h > mx.height() + MAX_SLACK:
            bad.append(f"{name}: больше предела {w}x{h} > {mx.width()}x{mx.height()}")
        if isinstance(widget, QPushButton) and h < MIN_BUTTON_H:
            bad.append(f"{name}: кнопка ниже {MIN_BUTTON_H} px")
    visible = [(n, p) for n, wd, p in elements if not wd.isHidden() and n in rects]
    for i, (a, pa) in enumerate(visible):
        for b, pb in visible[i + 1:]:
            if pa == pb and _overlap(rects[a], rects[b]):
                bad.append(f"{a} налезает на {b}")
    return bad


def check_style(tokens):
    """Контраст цветов темы со стилем: текст, приглушённый текст, кнопка-акцент, заголовок."""
    bad = []
    for fg, bg, lo in (("text", "bg", 4.5), ("text", "card", 4.5), ("muted", "bg", 3.0),
                       ("accent_text", "accent", 3.0), ("title", "bg", 3.0)):
        c = contrast(tokens[fg], tokens[bg])
        if not c >= lo:
            bad.append(f"контраст {fg}/{bg} {c:.2f} < {lo}")
    return bad


def check_tiles(net, code, kinds, limit):
    """Тайлы сети net и кода code (N, S, S, 3 uint8) одних ключей; kinds - вид каждого ключа
    (число: вид и змейка). Закон 1: ближайший к тайлу сети кодовый тайл - того же вида.
    Закон 2: среднее |разность| / 255 не больше limit."""
    bad = []
    a = net.reshape(len(net), -1).astype(np.float32) / 255.0
    b = code.reshape(len(code), -1).astype(np.float32) / 255.0
    diff = np.abs(a - b).mean(axis=1)
    for i in np.nonzero(diff > limit)[0][:5]:
        bad.append(f"тайл {i}: отличие {diff[i]:.3f} > {limit:.3f}")
    kinds = np.asarray(kinds)
    if len(np.unique(kinds)) > 1:
        # расстояние до каждого кодового тайла: |a|^2 - 2ab + |b|^2
        d = (a * a).sum(1)[:, None] - 2 * a @ b.T + (b * b).sum(1)[None, :]
        nearest = kinds[np.argmin(d, axis=1)]
        for i in np.nonzero(nearest != kinds)[0][:5]:
            bad.append(f"тайл {i}: похож на вид {nearest[i]}, а должен быть {kinds[i]}")
    return bad
