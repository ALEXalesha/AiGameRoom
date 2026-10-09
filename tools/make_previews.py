"""Кадры окна для README - без экрана, данные во временной папке.

    python tools/make_previews.py
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main():
    from aikit import offscreen
    offscreen.setup(force=True)
    from PySide6.QtWidgets import QApplication

    from shell.selftest import flush
    from shell.window import ShellWindow
    app = QApplication.instance() or QApplication([])
    w = ShellWindow(root=tempfile.mkdtemp(prefix="aigameroom-previews-"))
    w.resize(1240, 820)
    w.show()
    flush(app)
    docs = os.path.join(ROOT, "docs")
    shots = [("preview_home.png", "dark", "en", None), ("preview_home_ru_light.png", "light", "ru", None),
             ("preview_durak_tab.png", "dark", "en", "durak")]
    for name, theme, lang, game in shots:
        w.set_theme(theme)
        w.set_lang(lang)
        if game:
            w.open_game(game)
        else:
            w.tabs.setCurrentIndex(0)
        flush(app)
        w.grab().save(os.path.join(docs, name))
        print(name)
    w.close()
    flush(app)


if __name__ == "__main__":
    main()
