"""Загружается, но create_widget падает."""
GAME_INFO = {
    "id": "boom",
    "title": {"ru": "Взрыв", "en": "Boom"},
    "summary": {"ru": "падает при открытии", "en": "fails to open"},
    "preview": "x.png",
    "version": "1.0.0",
}


def create_widget(ctx):
    raise RuntimeError("стол не накрылся")
