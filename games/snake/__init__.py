"""Нейро-змейка (SnakeAi): две змейки на поле 32x32, вы против нейросети, а поле двигает
сеть-мир - кода правил змейки в игре нет.

Вход игры по контракту PythonAiGames: GAME_INFO и create_widget(ctx). Qt загружается
только в create_widget - сеть-мир, соперник и обучение работают без него.
"""
from games.snake.version import VERSION

GAME_INFO = {
    "id": "snake",
    "title": {"ru": "Нейро-змейка", "en": "Neuro Snake"},
    "summary": {"ru": "Змейка против нейросети на поле, которое двигает сеть-мир без кода правил",
                "en": "Snake against a neural network on a board moved by a world network with no rule code"},
    "preview": "docs/preview_menu.png",
    "version": VERSION,
}

APP_NAME = "SnakeAIGame"


def create_widget(ctx):
    """ctx: aikit.Context. Виджет с меню, матчем, статистикой и настройками."""
    from games.snake.ui.widget import GameWidget
    return GameWidget(ctx)
