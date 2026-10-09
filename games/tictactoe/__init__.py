"""Крестики-нолики (TicTacToeAi) в оболочке - переходник к контракту.

TicTacToeAi сделан до контракта: у него своё главное окно, свои настройки и тема, данные в
%LOCALAPPDATA%. Перевод на контракт - волна 7 (docs/plan.md, этап Г). До тех пор игра
приходит сюда копией tools/vendor_game.py (раскладка legacy), а этот файл и _adapter.py -
единственное, что написано здесь, а не взято из TicTacToeAi (games/vendor.json, "keep").
"""
from games.tictactoe.app.version import VERSION

GAME_INFO = {
    "id": "tictactoe",
    "title": {"ru": "Крестики-нолики", "en": "Tic-tac-toe"},
    "summary": {"ru": "Поля 3×3 и 5×5 против нейросети, которая научилась играть сама",
                "en": "3×3 and 5×5 boards against a neural network that taught itself"},
    "preview": "docs/preview_menu.png",
    "version": VERSION,
    "langs": ["ru"],
}


def create_widget(ctx):
    from games.tictactoe._adapter import TicTacToeWidget
    return TicTacToeWidget(ctx)
