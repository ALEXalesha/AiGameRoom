"""Мутационная проверка: нарочно ломает оболочку и смотрит, что тесты это ловят.

    python tools/mutate.py            # все мутанты
    python tools/mutate.py pause      # только с этим словом в имени

Мутант - замена строки в файле. Файл правится на месте, гоняются указанные тесты, затем
файл восстанавливается (в finally - и при Ctrl+C). Мутант «выжил», если тесты остались
зелёными: значит, этот кусок не проверен. Во время прогона файлы оболочки не править.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

GT, W, R, H = "shell/gametab.py", "shell/window.py", "shell/registry.py", "shell/home.py"
CC, VG, CT = "tools/contract_check.py", "tools/vendor_game.py", "shell/contract.py"
TS, TG, TC, TV = "tests/test_shell.py", "tests/test_games.py", "tests/test_contract_check.py", "tests/test_vendor.py"

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
     "            pass\n        self.current = new", f"{TS} -k \"hidden or switching\""),
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
]


def run(mutant, python):
    name, rel, old, new, tests = mutant
    path = os.path.join(ROOT, rel)
    with open(path, encoding="utf-8", newline="") as f:
        src = f.read()
    if src.count(old) != 1:
        return name, f"строка найдена {src.count(old)} раз"
    try:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src.replace(old, new))
        cmd = f'"{python}" -m pytest -q -x -p no:cacheprovider {tests}'
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900, shell=True)
        return name, "пойман" if r.returncode != 0 else "ВЫЖИЛ"
    finally:
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(src)


def main(argv):
    flt = argv[1] if len(argv) > 1 else ""
    mutants = [m for m in MUTANTS if flt in m[0]]
    alive = 0
    for m in mutants:
        name, verdict = run(m, sys.executable)
        print(f"{verdict:8} {name}", flush=True)
        alive += verdict != "пойман"
    print(f"итого {len(mutants)}, не пойманы {alive}")
    return 1 if alive else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main(sys.argv))
