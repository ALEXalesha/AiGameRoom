"""id не совпадает с именем папки."""
GAME_INFO = {
    "id": "other",
    "title": {"ru": "Чужая", "en": "Other"},
    "summary": {"ru": "id не как папка", "en": "id differs from folder"},
    "preview": "x.png",
    "version": "1.0.0",
}


def create_widget(ctx):
    raise AssertionError("не должна открываться")
