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
    # 0.2.2 (проверка графиков 17.10): числа над столбиками на легенде, тормоза длинного журнала
    ("графики: числа над столбиками без запаса", CH, "VALUE_ROOM = 16 ", "VALUE_ROOM = 0 ", f"{TCH} -k bar_values"),
    ("графики: налезания не замечаются", CH, "                if boxes[i][1].intersects(boxes[j][1]):",
     "                if False:", f"{TCH} -k overlaps_are"),
    ("графики: густая линия зигзагом", CH, "    if len(points) <= max(1, columns) or x1 <= x0:\n        return None",
     "    if True:\n        return None", f"{TCH} -k 'envelope or long_journal'"),
    ("графики: полоса без пиков", CH, "            b[1], b[2], b[3] = min(b[1], y), max(b[2], y), x",
     "            b[1], b[2], b[3] = b[1], b[2], x", f"{TCH} -k envelope"),
    ("контракт: статистика без графиков можно", CC, "    elif not charts:", "    elif False:",
     f"{TC} -k charts"),
]
MN, TMN = "aikit/menu.py", "aikit/tests/test_menu.py"
MUTANTS += [
    # 0.3.0: стартовое меню у каждой игры своё - общие только живой фон и законы раскладки
    ("меню: фон тикает скрытым", MN, "        want = self.isVisible() and not self.paused and not self.frozen",
     "        want = not self.paused and not self.frozen", f"{TMN} -k visible"),
    ("меню: пауза не останавливает", MN, "    def pause(self):\n        self.paused = True",
     "    def pause(self):\n        self.paused = False", f"{TMN} -k pause"),
    ("меню: время прыгает", MN, "        dt = min(self.MAX_STEP, self._clock.restart() / 1000.0)",
     "        dt = self._clock.restart() / 1000.0", f"{TMN} -k jump"),
    ("меню: заголовок не ужимается", MN, "        while px > self.min_px and self.text_width(px) > width:",
     "        while False:", f"{TMN} -k title"),
    ("меню: край не проверяется", MN, "        if not frame.contains(r):", "        if False:", f"{TMN} -k catches"),
    ("меню: наложение не видно", MN, "                if inter.width() > 1 and inter.height() > 1:",
     "                if False:", f"{TMN} -k catches"),
    ("меню: обрезка кнопки не видна", MN,
     "        return w.sizeHint().width() > w.width() or w.sizeHint().height() > w.height() + 1",
     "        return False", f"{TMN} -k catches"),
    ("меню: жирная выбранная не проверяется", MN, "            if bold_width(w) > w.width() + 1:\n                return True",
     "            if False:\n                return True", f"{TMN} -k bold"),
    ("меню: поля кнопки числом +30", "aikit/widgets.py", "    return QFontMetrics(bold).horizontalAdvance(text) + max(30, frame)",
     "    return QFontMetrics(bold).horizontalAdvance(text) + 30", f"{TMN} -k bold"),
    ("меню: обрезка заголовка не видна", MN, "    if isinstance(w, Title):\n        return w.clipped()",
     "    if isinstance(w, Title):\n        return False", f"{TMN} -k title_clipping"),
]

SK, TSK = "aikit/skin.py", "aikit/tests/test_skin.py"
MUTANTS += [
    # 0.4.0: настройки и статистика в стиле игры (автор 17.10) - общие механизм и законы
    ("скин: потолок высоты подписи не виден", SK,
     "        if w.isVisibleTo(body) and w.wordWrap() and w.maximumHeight() < QWIDGETSIZE_MAX:",
     "        if False:", f"{TSK} -k height_cap"),
    ("скин: страница шире окна не видна", SK, "        if body.width() > vw + 1:", "        if False:",
     f"{TSK} -k too_wide"),
    ("скин: обрезка графиков не видна", SK, "        if c.clipped:\n", "        if False:\n",
     f"{TSK} -k clipped_chart"),
    ("скин: графики в цветах aikit", CH, "        if self.skin is not None:\n            return self.skin.palette(self.theme)",
     "        if False:\n            return self.skin.palette(self.theme)", f"{TSK} -k take_card"),
    ("скин: рамка графика общая", CH, "        if self.skin is not None:\n            self.skin.paint_card(",
     "        if False:\n            self.skin.paint_card(", f"{TSK} -k take_card"),
    ("скин: фон рисуется каждый кадр", SK, "        if self._cache is None or self._cache[0] != key:",
     "        if True:", f"{TSK} -k painted_once"),
    ("скин: стрелка списка не в цвет", SK, '            c.set_arrow_color(pal["text"])', "            pass",
     f"{TSK} -k arrow"),
    ("скин: плитки не переносятся", SK,
     "        c = max(1, min(n, (width + self.GAP) // (self.min_tile + self.GAP)))", "        c = n",
     f"{TSK} -k tiles"),
    ("скин: таблица стилей не ставится", SK, "        self.setStyleSheet(self.skin.qss(theme))", "        pass",
     f"{TSK} -k tiles"),
    ("скин: заголовок без регистра игры", SK,
     "        super().setText(text.upper() if self.skin.heading_upper else text)",
     "        super().setText(text)", f"{TSK} -k heading"),
    ("скин: флажок меряется жирным", MN, "        if w.isCheckable() and not isinstance(w, (QCheckBox, QRadioButton)):",
     "        if w.isCheckable():", f"{TSK} -k checkbox_text"),
    ("меню: срезанная строка подписи не видна", MN, "        return widest > r.width() + 0.5 or tall > r.height() + 1",
     "        return widest > r.width() + 0.5", f"{TMN} -k multiline"),
    ("меню: срезанные хвосты букв не видны", MN, "    return max(0.0, fm.tightBoundingRect(text).bottom() - fm.descent())",
     "    return 0.0", f"{TMN} -k descenders"),
    ("скин: шапка таблицы белая", SK, 'QHeaderView {{ background: {p["surface"]}; border: none; }}\n', "",
     f"{TSK} -k header"),
    ("контракт: без стиля игры молча", CC, "    if not skin:", "    if False:", f"{TC} -k skin"),
]


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    from aikit.mutate import main
    sys.exit(main(ROOT, MUTANTS, sys.argv[1:]))
