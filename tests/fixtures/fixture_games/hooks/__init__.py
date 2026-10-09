"""Игра со своими pause/resume/shutdown - оболочка зовёт их."""
from PySide6.QtWidgets import QWidget

GAME_INFO = {
    "id": "hooks",
    "title": {"ru": "С крючками", "en": "Hooks"},
    "summary": {"ru": "образец с pause и resume", "en": "sample with pause and resume"},
    "preview": "none.png",
    "version": "0.2.0",
    "langs": ["ru"],
}

CALLS = []


class Widget(QWidget):
    def pause(self):
        CALLS.append("pause")

    def resume(self):
        CALLS.append("resume")

    def shutdown(self):
        CALLS.append("shutdown")
        return True


def create_widget(ctx):
    return Widget()
