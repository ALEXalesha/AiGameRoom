"""RockPaperAi: камень-ножницы-бумага против ИИ, который ловит привычки игрока.

Вход игры по контракту PythonAiGames: GAME_INFO и create_widget(ctx). Qt загружается
только в create_widget - правила и ИИ работают без него.
"""
from games.rockpaper.version import VERSION

GAME_INFO = {
    "id": "rockpaper",
    "title": {"ru": "Камень, ножницы, бумага", "en": "Rock Paper Scissors"},
    "summary": {"ru": "Камень-ножницы-бумага против ИИ, который замечает ваши привычки",
                "en": "Rock paper scissors against an AI that learns your habits"},
    "preview": "docs/preview.png",
    "version": VERSION,
}

APP_NAME = "RockPaperAi"


def create_widget(ctx):
    """ctx: aikit.Context. Виджет с меню, раундами, графиком и «Мыслями ИИ»."""
    from games.rockpaper.ui.widget import GameWidget
    return GameWidget(ctx)
