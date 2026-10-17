"""Стартовая расстановка раунда - картинка-данные, а не правило: две змейки длины 3 у
противоположных краёв головами друг к другу (на разных строках) и еда в центре."""
from games.snake.core.cells import build


def start_field(h=32, w=32):
    r0 = max(1, h // 2 - 3)
    r1 = h - 1 - r0
    snake0 = [(r0, 1), (r0, 2), (r0, 3)]
    snake1 = [(r1, w - 2), (r1, w - 3), (r1, w - 4)]
    return build(h, w, [snake0, snake1], food=[(h // 2, w // 2)])
