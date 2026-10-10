"""Строки оболочки на двух языках. Тест сверяет, что ключи в обоих одинаковые."""
from aikit.i18n import Translator

TABLES = {
    "ru": {
        "app": "ИИ-Игротека",
        "home": "Игры",
        "search": "Поиск игры",
        "theme": "Тема",
        "theme_dark": "Тёмная",
        "theme_light": "Светлая",
        "lang": "Язык",
        "volume": "Громкость",
        "play": "Играть",
        "opened": "Открыта",
        "version": "версия {v}",
        "ru_only": "Пока только по-русски",
        "broken": "Не загрузилась",
        "open_failed": "Не открылась: {e}",
        "nothing_found": "Ничего не нашлось",
        "no_games": "В папке games/ пока нет игр",
        "count": "Игр: {n}",
        "played": "партий {g} · побед {w} · лучшая серия {s}",
        "not_played": "ещё не играли",
        "played_total": "Партий во всех играх: {n}",
    },
    "en": {
        "app": "AI Game Room",
        "home": "Games",
        "search": "Find a game",
        "theme": "Theme",
        "theme_dark": "Dark",
        "theme_light": "Light",
        "lang": "Language",
        "volume": "Volume",
        "play": "Play",
        "opened": "Open",
        "version": "version {v}",
        "ru_only": "Russian only for now",
        "broken": "Failed to load",
        "open_failed": "Failed to open: {e}",
        "nothing_found": "Nothing found",
        "no_games": "No games in the games/ folder yet",
        "count": "Games: {n}",
        "played": "{g} games · {w} wins · best streak {s}",
        "not_played": "not played yet",
        "played_total": "Games played in total: {n}",
    },
}


def translator(lang):
    return Translator(TABLES, lang)
