"""Матч в окне без Qt: человек (или бот в показе) против ИИ, подглядывание, итог.

Режимы: 'play' - человек против ИИ, 'demo' - ИИ против бота с привычкой.

Подсчёт (решение автора 16.10, как в Дураке): матч, брошенный после первого сыгранного
раунда (новый матч, меню, закрытие окна), - поражение; до первого раунда - не считается.
"""
from games.rockpaper.ai.bots import make_bot
from games.rockpaper.ai.player import make_ai
from games.rockpaper.core.match import Match

MODES = ("play", "demo")


class Session:
    def __init__(self, k=3, length=100, level="strong", mode="play", bot="cycle", seed=0):
        if mode not in MODES:
            raise ValueError(mode)
        self.k = k
        self.level = level
        self.mode = mode
        self.bot_key = bot
        self.seed = seed
        self.match = Match(k, length)
        self.ai = make_ai(level, k, seed=seed)
        self.bot = make_bot(bot, k, seed=seed + 1) if mode == "demo" else None
        self.peeked = False            # смотрел прогноз до хода - в статистику не идёт
        self.recorded = False
        self.abandoned = False         # брошен до конца (итог записан в этот момент)
        self.commit = self.match.prepare(self.ai)

    @property
    def over(self):
        return self.match.over

    @property
    def rounds(self):
        return self.match.rounds

    def pending_thoughts(self):
        p = self.match.pending
        return p.thoughts if p is not None else None

    def last_reveal(self):
        return self.match.reveals[-1] if self.match.reveals else None

    def play(self, human):
        """Ход человека (или бота). Возвращает Reveal; ИИ сразу выбирает ход следующего раунда."""
        rv = self.match.play(human, self.ai)
        self.commit = None if self.over else self.match.prepare(self.ai)
        return rv

    def demo_step(self):
        return self.play(self.bot.move(self.match.history()))

    def end(self):
        self.match.end()
        self.commit = None

    def outcome_for_human(self):
        if self.mode != "play":
            return None
        return self.match.outcome_for_human()

    def abandon_outcome(self):
        """Итог, если матч бросить сейчас: None - не считается (показ, матч окончен или ещё
        ни одного раунда), иначе поражение."""
        if self.mode != "play" or self.over or not self.rounds:
            return None
        return "loss"

    def counts(self):
        return not self.peeked and self.mode == "play" and bool(self.rounds)

    def stats_key(self):
        return f"{self.k}/{self.level}"
