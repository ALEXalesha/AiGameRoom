"""Матч без Qt: раунды, счёт, отсчёт, очередь клавиш, события для звуков.

Правил змейки здесь нет: поле двигает только мир (world.step - сеть-мир), игра лишь подаёт
ему ход игрока и ход соперника и читает ответ. Время подаётся извне через update(dt_ms),
поэтому тесты не ждут.

Фазы: COUNTDOWN (3-2-1) -> PLAYING -> ROUND_OVER (пауза) -> COUNTDOWN ... -> MATCH_OVER.
События (take_events): countdown, go, eat0, eat1, crash, round_win, round_lose, round_draw,
win, lose - всё с точки зрения игрока (змейка 0).
"""
from collections import deque

from games.snake.core import cells
from games.snake.core.cells import NONE
from games.snake.core.start import start_field

COUNTDOWN, PLAYING, ROUND_OVER, MATCH_OVER = "countdown", "playing", "round_over", "match_over"

COUNT_STEP_MS = 700        # одна цифра отсчёта
ROUND_PAUSE_MS = 1200      # пауза после раунда
QUEUE_SIZE = 2             # столько нажатий помнится между ходами
MAX_STEPS_PER_UPDATE = 4   # после долгой заминки не догонять время пачкой ходов


class Match:
    def __init__(self, world, opponent, rng, target=3, speed_ms=110, size=32):
        self.world = world
        self.opponent = opponent
        self.rng = rng
        self.target = target
        self.speed_ms = speed_ms
        self.size = size
        self.score = [0, 0]
        self.round = 0
        self.eaten = [0, 0]           # за весь матч
        self.round_eaten = [0, 0]     # за текущий раунд
        self.longest = [0, 0]
        self.winner = None
        self.paused = False
        self.version = 0              # растёт, когда есть что перерисовать
        self.events = []
        self.keys = deque()
        self._start_round()

    # --- снаружи ---------------------------------------------------------------------

    def press(self, direction):
        """Нажатие игрока. Повтор того же направления места не занимает."""
        if self.paused or self.phase not in (COUNTDOWN, PLAYING):
            return
        if self.keys and self.keys[-1] == direction:
            return
        if len(self.keys) < QUEUE_SIZE:
            self.keys.append(direction)

    def update(self, dt_ms):
        if self.paused or dt_ms <= 0 or self.phase == MATCH_OVER:
            return
        if self.phase == COUNTDOWN:
            self._timer -= dt_ms
            while self.phase == COUNTDOWN and self._timer <= 0:
                self.count -= 1
                self.version += 1
                if self.count > 0:
                    self._timer += COUNT_STEP_MS
                    self._emit("countdown")
                else:
                    self.phase = PLAYING
                    self._acc = 0
                    self._emit("go")
        elif self.phase == PLAYING:
            self._acc += dt_ms
            steps = 0
            while self.phase == PLAYING and self._acc >= self.speed_ms:
                self._acc -= self.speed_ms
                self.step()
                steps += 1
                if steps >= MAX_STEPS_PER_UPDATE:
                    self._acc = min(self._acc, self.speed_ms - 1)
                    break
        elif self.phase == ROUND_OVER:
            self._timer -= dt_ms
            if self._timer <= 0:
                self._start_round()

    def take_events(self):
        out, self.events = self.events, []
        return out

    def lengths(self):
        return cells.length(self.field, 0), cells.length(self.field, 1)

    # --- ход ---------------------------------------------------------------------------

    def step(self):
        a0 = self.keys.popleft() if self.keys else NONE
        a1 = int(self.opponent.act(self.field, 1))
        res = self.world.step(self.field, a0, a1, self.rng)
        self.food_probs = res.food_probs
        self.confidence = res.confidence
        crashed = [bool(c) for c in res.crashed]
        if res.field is not None:
            # Защита от сбоя сети, а не правило игры: если сеть выдала поле без головы
            # змейки, считаем, что эта змейка врезалась, - иначе раунд завис бы навсегда.
            for s in (0, 1):
                if cells.head(res.field, s) is None:
                    crashed[s] = True
        elif not any(crashed):
            crashed = [True, True]     # тоже защита от сбоя: поля нет, а события молчат
        self.version += 1
        if any(crashed):
            self._end_round(tuple(crashed))
            return
        self.field = res.field
        for s in (0, 1):
            if res.ate[s]:
                self.eaten[s] += 1
                self.round_eaten[s] += 1
                self._emit(f"eat{s}")
        self._note_lengths()

    # --- внутри ------------------------------------------------------------------------

    def _emit(self, event):
        self.events.append(event)

    def _note_lengths(self):
        for s, n in enumerate(self.lengths()):
            self.longest[s] = max(self.longest[s], n)

    def _start_round(self):
        self.round += 1
        self.field = start_field(self.size, self.size)
        self.food_probs = None
        self.confidence = None
        self.crashed = (False, False)
        self.round_result = None
        self.round_eaten = [0, 0]
        self.keys.clear()
        self.phase = COUNTDOWN
        self.count = 3
        self._timer = COUNT_STEP_MS
        self._acc = 0
        self.version += 1
        self._note_lengths()
        self._emit("countdown")

    def _end_round(self, crashed):
        self.crashed = crashed
        self._emit("crash")
        if crashed[0] and crashed[1]:
            self.round_result = "draw"
        elif crashed[1]:
            self.round_result = "win"
            self.score[0] += 1
        else:
            self.round_result = "lose"
            self.score[1] += 1
        self._emit("round_" + self.round_result)
        if max(self.score) >= self.target:
            self.phase = MATCH_OVER
            self.winner = 0 if self.score[0] >= self.target else 1
            self._emit("win" if self.winner == 0 else "lose")
        else:
            self.phase = ROUND_OVER
            self._timer = ROUND_PAUSE_MS
