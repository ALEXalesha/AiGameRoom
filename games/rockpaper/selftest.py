"""Самопроверка без экрана: python main.py --selftest итог.txt.

Нужна прежде всего собранному exe: он без консоли, поэтому итог пишется в файл. Окно
создаётся offscreen, данные игрока - во временной папке. Проверяется: правила обоих
вариантов, сильный ИИ против ботов с привычками, и матч через окно - бот «как человек»
нажимает знаки, отпечаток каждого раунда сверяется.
"""
import os
import tempfile
import time
import traceback


def selftest(out_path):
    lines = []
    code = 0
    try:
        import aikit
        from games.rockpaper.ai.arena import run, summary
        from games.rockpaper.core.rules import beats
        from games.rockpaper.version import VERSION

        lines.append(f"RockPaperAi {VERSION} самопроверка (aikit {aikit.__version__})")
        for k in (3, 5):
            for m in range(k):
                if sum(beats(a, m, k) for a in range(k)) != (k - 1) // 2:
                    raise RuntimeError(f"правила на {k} знаков нарушены")
        lines.append("правила: 3 и 5 знаков, каждый знак бьёт половину остальных")
        for bot in ("cycle", "wsls", "repeat", "random"):
            t0 = time.time()
            s = summary(run("strong", bot, 2, 100, 1, 3))
            lines.append(f"сильный ИИ против «{bot}»: побед ИИ {s['all']['win']:.2f}, "
                         f"после 30-го раунда {s['after30']['win']:.2f}, {time.time() - t0:.2f} с")
            if bot in ("cycle", "wsls") and s["after30"]["win"] < 0.9:
                raise RuntimeError(f"ИИ не поймал привычку «{bot}»")
        from aikit import offscreen
        offscreen.setup(force=True)
        home = tempfile.mkdtemp(prefix="rockpaperai-selftest-")
        os.environ["ROCKPAPERAI_HOME"] = home
        from PySide6.QtWidgets import QApplication

        from aikit.host import make_window
        from games.rockpaper import APP_NAME, GAME_INFO, create_widget
        from games.rockpaper.ai.bots import make_bot
        app = QApplication.instance() or QApplication([])
        window, ctx = make_window(GAME_INFO, create_widget, APP_NAME, root=home)
        window.show()
        g = window.game
        for k in (3, 5):
            t0 = time.time()
            g.change("k", k)
            g.change("length", 100)
            g.start_match(seed=k)
            bot = make_bot("human", k, seed=k)
            while not g.session.over:
                g.on_sign(bot.move(g.session.match.history()))
                if not g.session.last_reveal().verified(k):
                    raise RuntimeError("отпечаток хода ИИ не совпал")
            app.processEvents()
            image = window.grab().toImage()
            if image.isNull() or image.width() < 300:
                raise RuntimeError("окно не нарисовалось")
            sc = g.session.match.score()
            lines.append(f"окно, {'3 знака' if k == 3 else '5 знаков'}: 100 раундов бота «как человек», счёт {sc['wins']}:{sc['losses']} "
                         f"(ничьих {sc['ties']}), отпечатки сошлись, кадр {image.width()}x{image.height()}, "
                         f"{time.time() - t0:.2f} с")
        t0 = time.time()
        window.close()
        app.processEvents()
        lines.append(f"окно закрыто за {time.time() - t0:.2f} с")
        lines.append("ИТОГ: работает")
    except Exception:  # noqa: BLE001 - любая ошибка должна попасть в файл
        lines.append("ИТОГ: ошибка")
        lines.append(traceback.format_exc())
        code = 1
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return code
