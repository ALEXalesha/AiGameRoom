"""Шум оформления и «ручки» кода.

Шум z (4 числа от -1 до 1) - вход обеих сетей-оформителей. Код-учитель по тому же шуму делает
свой вариант окна: поля, промежутки, скругления, размер шрифта и тон акцентного цвета. Сеть
учится на этих вариантах, а в игре шум берётся случайно при каждом запуске - окно почти то же,
но с отличиями. z = 0 - ровно окно 1.1.0.
"""
import colorsys
from typing import NamedTuple

import numpy as np

Z_DIM = 4
STYLE_COLORS = ("accent", "accent_hover", "accent_pressed", "title", "selection")
STYLE_DIM = 2 + 3 * len(STYLE_COLORS)


class Knobs(NamedTuple):
    margin: float      # множитель полей экрана и карточек
    spacing: float     # множитель промежутков между элементами
    font: float        # множитель размеров шрифта
    radius: float      # скругление кнопок, px (карточки +4)
    hue: float         # поворот тона акцентных цветов, градусы


# Шрифт - пять размеров, а не плавная ручка: высота строки текста меняется ступеньками по
# пикселю, и между обученными уровнями сеть-дизайнер промахивалась по высоте строк (замер
# 17.10: 5 запусков из 40 - запасной вариант у строки «Скорость» настроек).
FONT_LEVELS = (-1.0, -0.5, 0.0, 0.5, 1.0)


def sample_z(rng):
    z = rng.uniform(-1.0, 1.0, Z_DIM)
    z[2] = FONT_LEVELS[int(rng.integers(len(FONT_LEVELS)))]
    return z


def knobs(z):
    z = np.clip(np.asarray(z, dtype=np.float64).reshape(Z_DIM), -1.0, 1.0)
    return Knobs(margin=1 + 0.2 * z[0], spacing=1 + 0.15 * z[1], font=1 + 0.04 * z[2],
                 radius=10 + 3 * z[1], hue=14 * z[3])


def _hex(rgb):
    return "#" + "".join(f"{int(round(min(max(v, 0.0), 1.0) * 255)):02x}" for v in rgb)


def _rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rotate_hue(color, degrees):
    """Тот же цвет с тоном, повёрнутым на degrees; светлота и насыщенность (HLS) те же."""
    if degrees == 0:
        return color
    h, l, s = colorsys.rgb_to_hls(*_rgb(color))
    return _hex(colorsys.hls_to_rgb((h + degrees / 360.0) % 1.0, l, s))


def code_style(tokens, z):
    """Стиль окна, который по шуму z выбрал бы код: {font, radius, colors}. tokens - цвета темы."""
    k = knobs(z)
    return {"font": k.font, "radius": k.radius,
            "colors": {name: rotate_hue(tokens[name], k.hue) for name in STYLE_COLORS}}


def style_vector(style):
    """Стиль -> вектор выхода сети: font, radius/10, затем RGB цветов STYLE_COLORS (0..1)."""
    out = [style["font"], style["radius"] / 10.0]
    for name in STYLE_COLORS:
        out.extend(_rgb(style["colors"][name]))
    return np.asarray(out, dtype=np.float32)


def style_from_vector(v):
    v = np.asarray(v, dtype=np.float64)
    colors = {name: _hex(v[2 + 3 * i: 5 + 3 * i]) for i, name in enumerate(STYLE_COLORS)}
    return {"font": float(v[0]), "radius": float(v[1] * 10.0), "colors": colors}


def luminance(color):
    def lin(c):
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in _rgb(color))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """Контраст двух цветов по WCAG: 1 - одинаковые, 21 - чёрный на белом."""
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)
