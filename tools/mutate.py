"""Мутационная проверка: нарочно ломает оболочку и смотрит, что тесты это ловят.

    python tools/mutate.py            # все мутанты
    python tools/mutate.py pause      # только с этим словом в имени

Прогон - aikit.mutate: сначала тесты без мутанта (красные - стоп), зависание - «пойман»,
файл восстанавливается в finally. Мутант «выжил», если тесты остались зелёными: значит, этот
кусок не проверен. Во время прогона файлы оболочки не править.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GT, W, R, H = "shell/gametab.py", "shell/window.py", "shell/registry.py", "shell/home.py"
CC, VG, CT = "tools/contract_check.py", "tools/vendor_game.py", "shell/contract.py"
TS, TG, TC, TV = "tests/test_shell.py", "tests/test_games.py", "tests/test_contract_check.py", "tests/test_vendor.py"
CH, GL, TCH, TGL = "aikit/charts.py", "aikit/gamelog.py", "aikit/tests/test_charts.py", "aikit/tests/test_gamelog.py"

# (имя, файл, было, стало, тесты)
MUTANTS = [
    ("pause: таймеры не стоят", GT, "            for t in self._timers:\n                t.stop()",
     "            pass", f"{TS} -k hidden"),
    ("pause: фильтр не гасит заведённый таймер", GT, "            obj.stop()\n", "", f"{TS} -k hidden"),
    ("pause: фильтр не ставится", GT, "                t.installEventFilter(self._gate)", "                pass",
     f"{TS} -k hidden"),
    ("resume: таймеры не запускаются", GT, "            for t in self._timers:\n                t.start()",
     "            pass", f"{TS} -k hidden"),
    ("pause: свои pause/resume игры не зовутся", GT, '        has, _ = self._call("pause")',
     "        has = False", f"{TS} -k switching"),
    ("shutdown: игра не останавливается", GT, 'has, result = self._call("shutdown")',
     "has, result = False, None", f"{TS} -k close_tab"),
    ("shutdown: долгий не замечен", GT, "if self.shutdown_seconds > SHUTDOWN_LIMIT:", "if False:",
     f"{TS} -k slow"),
    ("закрытие: вкладка не удаляется", W, "        tab.deleteLater()\n", "", f"{TS} -k close_tab"),
    ("переключение: скрытая игра не на паузе", W, "            self.current.pause()\n        self.current = new",
     "            pass\n        self.current = new", f"{TS} -k 'hidden or switching'"),
    ("свёрнутое окно: игра идёт", W,
     "            if self.windowState() & Qt.WindowState.WindowMinimized:\n                self.current.pause()",
     "            if self.windowState() & Qt.WindowState.WindowMinimized:\n                pass", f"{TS} -k minimized"),
    ("тема не доходит до игр", W, "            g.ctx.set_theme(name)", "            pass", f"{TS} -k theme"),
    ("тема из игры не доходит до оболочки", W, "            self.set_theme(ctx.theme)", "            pass",
     f"{TS} -k theme_changed_inside"),
    ("громкость не общая", W, "            g.ctx.set_volume(volume)", "            pass", f"{TS} -k volume"),
    ("сломанная игра роняет список", R, "except Exception as e:  # noqa: BLE001 - любая ошибка игры",
     "except SyntaxError as e:  # noqa: BLE001 - любая ошибка игры", f"{TS} -k registry"),
    ("id не сверяется с папкой", R, 'if entry.info["id"] != name:', "if False:", f"{TS} -k registry"),
    ("версия любая", CT, r'VERSION_RE = re.compile(r"^\d+\.\d+\.\d+', r'VERSION_RE = re.compile(r"^\d+', f"{TC} -k info"),
    ("create_widget с двумя параметрами", CT, "if len(required) > 1 or not params:", "if not params:",
     f"{TS} -k registry"),
    ("карточка сломанной игры с кнопкой", H, "self.play.setVisible(entry.ok)", "self.play.setVisible(True)",
     f"{TS} -k cards_show"),
    ("статистика не обновляется после игры", W, "            self.home.retranslate()           # статистика",
     "            self.home.sync()           # статистика", f"{TS} -k statistic"),
    ("статистика не читается", H, '"stats.json")).totals()', '"stats.jsn")).totals()', f"{TS} -k statistic"),
    ("поиск с учётом регистра", H, "return query.casefold() in hay.casefold()", "return query in hay",
     f"{TS} -k search"),
    ("контракт: pygame можно", CC, 'if top == "pygame":', 'if top == "pygame_":', f"{TC} -k violation"),
    ("контракт: Qt в правилах можно", CC, "elif in_core and top in", "elif False and top in", f"{TC} -k violation"),
    ("контракт: windows-latest на Gitea", CC, r'r"^\s*runs-on:\s*windows\s*$"', r'r"runs-on:\s*windows"',
     f"{TC} -k violation"),
    ("контракт: запись мимо data_dir", CC, "    if touched:", "    if False:", f"{TC} -k slow_shutdown"),
    ("контракт: личный путь можно", CC, "        if USER_PATH_RE.search(text):", "        if False:",
     f"{TC} -k violation"),
    ("копия: отступ теряется", VG, "        lines[row] = head + changed", "        lines[row] = changed",
     f"{TV} -k lazy"),
    ("копия: переходник не сохраняется", VG, 'for rel in entry.get("keep", []):', "for rel in []:",
     f"{TV} -k legacy"),
    ("копия: import game.x молча", VG, 'problems.append(f"строка {node.lineno}: import {alias.name} - замените на from ... import")\n                continue',
     "pass", f"{TV} -k unsafe"),
    ("крестики: resume не будит сеть", "games/tictactoe/_adapter.py", "            game.after_change()",
     "            pass", f"{TG} -k tictactoe_net"),
    # графики статистики (aikit 0.2.0)
    ("графики: линия из одной точки", CH, "        return len(self.points) >= 2", "        return len(self.points) >= 1",
     f"{TCH} -k one_point"),
    ("графики: обрезка не замечается", CH, "            self.clipped.append(text)", "            pass",
     f"{TCH} -k clipping_is_noticed"),
    ("графики: легенда не переносится", CH, "        one_line = not chunks or title_w + 16 + all_w <= head_w",
     "        one_line = True", f"{TCH} -k 'keep_all_labels or second_line'"),
    ("графики: поле для чисел узкое", CH, "widest * SLACK + 12", "widest * 0.5", f"{TCH} -k big_numbers"),
    ("графики: тема не меняется", CH, "        self.theme = name\n        self.update()", "        self.update()",
     f"{TCH} -k theme"),
    ("графики: всегда две колонки", CH, "        return 2 if width >= 2 * self.min_col + GAP else 1", "        return 2",
     f"{TCH} -k grid_two"),
    ("графики: высота сетки не сообщается", CH, "        return y + max(c.height() for c, _, _ in last)", "        return 0",
     f"{TCH} -k grid_two"),
    ("графики: ровная линия уходит ниже нуля", CH, "(max(0.0, lo - pad) if lo >= 0 else lo - pad)", "lo - pad",
     f"{TCH} -k flat_zero"),
    ("графики: дробный шаг у целых", CH, "        step = max(1.0, step if step >= 1 else 1.0)", "        pass",
     f"{TCH} -k flat_zero"),
    ("журнал: уровни по алфавиту", GL, "    groups = [lv for lv in levels if sum(count[lv].values())]",
     "    groups = sorted(lv for lv in levels if sum(count[lv].values()))", f"{TGL} -k by_level"),
    ("журнал: окно не скользит", GL, "        if window is not None and k >= window:", "        if False:",
     f"{TGL} -k rolling"),
    ("журнал: ничья как поражение", GL, 'VALUE = {"win": 1.0, "draw": 0.5, "loss": 0.0}',
     'VALUE = {"win": 1.0, "draw": 0.0, "loss": 0.0}', f"{TGL} -k rolling"),
    ("журнал: мусорные поля пишутся", GL, "    return is_num(v) or isinstance(v, bool) or",
     "    return True or", f"{TGL} -k dropped"),
    ("журнал: номер берётся из записи", GL, '        g = {"n": self.next, **_tidy(game)}',
     '        g = {**_tidy(game), "n": game.get("n", self.next)}', f"{TGL} -k continue"),
    ("журнал: рекорд не копится", GL, "        if best is None or (v > best if better == \"max\" else v < best):",
     "        if True:", f"{TGL} -k best_curve"),
    ("журнал: серия не рвётся", GL, '        cur = cur + 1 if g["outcome"] == "win" else 0', "        cur = cur + 1",
     f"{TGL} -k streaks"),
    ("контракт: статистика без графиков можно", CC, "    elif not charts:", "    elif False:",
     f"{TC} -k charts"),
]


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    from aikit.mutate import main
    sys.exit(main(ROOT, MUTANTS, sys.argv[1:]))
