"""AiGameRoom (ИИ-Игротека): все игры с ИИ в одном окне.

    python main.py                         # оболочка
    python main.py --game durak            # сразу открыть игру
    python main.py --list                  # какие игры нашлись и какие не загрузились
    python main.py --offscreen             # без экрана (проверки)
    python main.py --selftest итог.txt     # самопроверка без экрана, итог в файл
"""
import argparse
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def main(argv=None):
    ap = argparse.ArgumentParser(description="AiGameRoom - игры с ИИ")
    ap.add_argument("--game", metavar="ID", help="сразу открыть игру")
    ap.add_argument("--list", action="store_true", help="список игр")
    ap.add_argument("--offscreen", action="store_true", help="без экрана")
    ap.add_argument("--selftest", metavar="ФАЙЛ", nargs="?", const="selftest.txt",
                    help="открыть и закрыть каждую игру без экрана, итог в файл")
    args = ap.parse_args(argv)
    if args.selftest:
        from shell.selftest import selftest
        return selftest(args.selftest)
    if args.list:
        from shell import registry
        for e in registry.discover():
            state = f"{e.info['version']}" if e.ok else f"НЕ ЗАГРУЗИЛАСЬ: {e.error}"
            print(f"{e.folder:12} {e.title('ru') if e.ok else '':20} {state}")
        return 0
    if args.offscreen:
        from aikit import offscreen
        offscreen.setup(force=True)
    from PySide6.QtWidgets import QApplication

    from shell.window import APP_NAME, ShellWindow
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    window = ShellWindow()
    window.memory.show()
    if args.game and window.open_game(args.game) is None:
        print(f"игра {args.game} не открылась", file=sys.stderr)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
