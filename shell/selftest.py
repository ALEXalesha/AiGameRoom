"""Самопроверка без экрана: открыть и закрыть каждую игру, сменить тему и язык, итог в файл.

Нужна прежде всего собранному exe: он без консоли. Данные - во временной папке, настройки
и статистика игрока не трогаются.
"""
import os
import tempfile
import time
import traceback


def flush(app):
    """Отработать отложенные удаления (deleteLater): processEvents их сам не делает."""
    import gc

    from PySide6.QtCore import QCoreApplication, QEvent
    for _ in range(3):
        app.processEvents()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def run_checks(lines):
    from PySide6.QtWidgets import QApplication

    from shell.version import VERSION
    from shell.window import ShellWindow

    app = QApplication.instance() or QApplication([])
    window = ShellWindow()
    window.show()
    app.processEvents()
    lines.append(f"AiGameRoom {VERSION} самопроверка")
    for e in window.entries:
        if not e.ok:
            lines.append(f"{e.folder}: не загрузилась - {e.error}")
    base = len(QApplication.allWidgets())
    for e in [e for e in window.entries if e.ok]:
        started = time.perf_counter()
        tab = window.open_game(e.id)
        if tab is None:
            raise RuntimeError(f"{e.id}: не открылась - {e.open_error}")
        app.processEvents()
        for theme, lang in (("light", "en"), ("dark", "ru")):
            window.set_theme(theme)
            window.set_lang(lang)
            app.processEvents()
        window.tabs.setCurrentIndex(0)
        window.tabs.setCurrentWidget(tab)
        image = window.grab().toImage()
        if image.isNull() or image.width() < 100:
            raise RuntimeError(f"{e.id}: окно не нарисовалось")
        seconds = window.close_game(tab)
        flush(app)
        left = len(QApplication.allWidgets()) - base
        lines.append(f"{e.id} {e.info['version']}: открыта и закрыта, shutdown {seconds:.2f} с, "
                     f"виджетов осталось {left}, {time.perf_counter() - started:.2f} с")
        if left > 0:
            raise RuntimeError(f"{e.id}: после закрытия осталось {left} виджетов")
    window.close()
    app.processEvents()
    if window.problems:
        raise RuntimeError("ошибки игр: " + "; ".join(window.problems))
    if not any(e.ok for e in window.entries):
        raise RuntimeError("ни одной игры")


def selftest(out_path):
    lines, code = [], 0
    try:
        from aikit import offscreen
        offscreen.setup(force=True)
        os.environ["AIGAMEROOM_HOME"] = tempfile.mkdtemp(prefix="aigameroom-selftest-")
        run_checks(lines)
        lines.append("ИТОГ: работает")
    except Exception:  # noqa: BLE001 - любая ошибка должна попасть в файл
        lines.append("ИТОГ: ошибка")
        lines.append(traceback.format_exc())
        code = 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code
