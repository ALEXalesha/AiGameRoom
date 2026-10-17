"""Сеть-дизайнер: по экрану, размеру окна, теме, языку, видимости и шуму выдаёт раскладку
экрана (прямоугольник каждого элемента) и стиль окна (шрифт, скругление, акцентные цвета).

    вход 16: ширина/1000, высота/1000, экран (4), тема (2), язык (2), видимость (2), шум (4)
      -> Dense 384 -> ReLU -> Dense 384 -> ReLU -> Dense 69
    выход: 13 мест x (x, y, w, h)/1000 и 17 чисел стиля (game/design/knobs.style_vector)

Учится на раскладках кода (Qt-раскладки экранов при ручках по тому же шуму) - сотни размеров
окна, обе темы, оба языка. Места экрана - элементы его elements() по порядку; лишние места
у маленьких экранов не учатся и не читаются.
"""
import numpy as np

from games.snake.design.knobs import STYLE_DIM, Z_DIM, style_from_vector
from games.snake.design.mlp import MLP

SCREENS = ("menu", "match", "stats", "settings")
SLOTS = {
    "menu": ("logo", "title", "subtitle", "play", "stats", "settings", "quit", "message", "info"),
    "match": ("board", "panel", "score_block", "lengths_block", "conf_block", "opponent_block", "keys",
              "pause"),
    "stats": ("title", "back", "scroll"),
    "settings": ("title", "back", "card_game", "game_head", "row_speed", "row_opponent", "row_food_map",
                 "card_view", "view_head", "row_volume", "row_theme", "row_language", "row_palette"),
}
MAX_SLOTS = max(len(v) for v in SLOTS.values())
THEMES = ("dark", "light")
LANGS = ("ru", "en")
IN = 2 + len(SCREENS) + len(THEMES) + len(LANGS) + 2 + Z_DIM
OUT = 4 * MAX_SLOTS + STYLE_DIM
SCALE = 1000.0
# Запас места: сеть учится на прямоугольниках кода, раздвинутых на ROOM px с каждой стороны.
# Код ставит элементы впритык к их наименьшему размеру, и ошибка сети в 1-2 px вниз
# обрезала бы текст; с запасом промахи уходят в лишний пиксель воздуха (промежутки 6-18 px).
ROOM = 1


def inputs(screen, w, h, theme, lang, flags, z):
    x = np.zeros(IN, np.float32)
    x[0], x[1] = w / SCALE, h / SCALE
    x[2 + SCREENS.index(screen)] = 1
    x[6 + (THEMES.index(theme) if theme in THEMES else 0)] = 1
    x[8 + (LANGS.index(lang) if lang in LANGS else 0)] = 1
    x[10], x[11] = flags
    x[12:] = np.asarray(z, np.float32).reshape(Z_DIM)
    return x


def target(screen, rects, style_vec):
    """Выход сети для учителя и маска мест, которые учатся (элемент виден)."""
    y = np.zeros(OUT, np.float32)
    mask = np.zeros(OUT, np.float32)
    for i, name in enumerate(SLOTS[screen]):
        if name in rects:
            x0, y0, w, h = rects[name]
            y[4 * i:4 * i + 4] = np.asarray((x0 - ROOM, y0 - ROOM, w + 2 * ROOM, h + 2 * ROOM), np.float32) / SCALE
            mask[4 * i:4 * i + 4] = 1
    y[4 * MAX_SLOTS:] = style_vec
    mask[4 * MAX_SLOTS:] = 1
    return y, mask


def size_index():
    """Номера выходов ширины и высоты мест - их недобор обучение штрафует сильнее."""
    return np.array([4 * i + j for i in range(MAX_SLOTS) for j in (2, 3)])


def rects_from(screen, out):
    """Выход сети -> {имя: (x, y, w, h)} в целых пикселях."""
    out = np.asarray(out, np.float64)
    rects = {}
    for i, name in enumerate(SLOTS[screen]):
        x, y, w, h = out[4 * i:4 * i + 4] * SCALE
        x0, y0 = int(round(x)), int(round(y))
        rects[name] = (x0, y0, int(round(x + w)) - x0, int(round(y + h)) - y0)
    return rects


class DesignerNet:
    def __init__(self, hidden=384, rng=None, mlp=None):
        self.mlp = mlp if mlp is not None else MLP((IN, hidden, hidden, OUT), rng=rng)

    def params(self):
        return self.mlp.params()

    def forward(self, x):
        return self.mlp.forward(x)

    def backward(self, dy):
        return self.mlp.backward(dy)

    def layout(self, screen, w, h, theme, lang, flags, z):
        out = self.forward(inputs(screen, w, h, theme, lang, flags, z)[None])[0]
        return rects_from(screen, out)

    def style(self, theme, lang, z):
        """Стиль окна - ответ сети для обычного окна меню (стиль от размера не зависит)."""
        out = self.forward(inputs("menu", 1040, 720, theme, lang, (0, 0), z)[None])[0]
        return style_from_vector(out[4 * MAX_SLOTS:])

    def save(self, path):
        self.mlp.save(path)

    @classmethod
    def load(cls, path):
        mlp = MLP.load(path)
        if mlp.sizes[0] != IN or mlp.sizes[-1] != OUT:
            raise ValueError(f"{path}: сеть не дизайнера {mlp.sizes}")
        return cls(mlp=mlp)
