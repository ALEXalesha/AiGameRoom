"""Матчи ИИ против ботов для паспорта и тестов. Всё с зёрнами: матч i против бота b
пересчитывается отдельно и совпадает раунд в раунд."""
from games.rockpaper.ai.bots import make_bot
from games.rockpaper.ai.player import make_ai
from games.rockpaper.core.match import Match
from games.rockpaper.core.rules import LOSS, TIE, WIN


def match_seed(seed, i):
    return int(seed) * 1000003 + int(i)


def play(ai, bot, rounds, k=3):
    """Матч на rounds раундов через Match (с фиксацией хода). Возвращает Match."""
    m = Match(k, rounds)
    while not m.over:
        m.prepare(ai)
        m.play(bot.move(m.history()), ai)
    return m


def ai_results(m):
    """Строка итогов для ИИ: W - ИИ выиграл раунд, T - ничья, L - проиграл."""
    return "".join({LOSS: "W", TIE: "T", WIN: "L"}[r.result] for r in m.rounds)


def run(level, bot_key, matches, rounds, seed, k=3, indices=None):
    """Строки итогов ИИ по матчам."""
    out = []
    for i in (range(matches) if indices is None else indices):
        s = match_seed(seed, i)
        ai = make_ai(level, k, seed=s)
        bot = make_bot(bot_key, k, seed=s + 1)
        out.append(ai_results(play(ai, bot, rounds, k)))
    return out


def summary(lines):
    """Доли по всем раундам и по раундам после 30-го (когда привычки уже пойманы)."""
    def part(rs):
        n = max(len(rs), 1)
        w, t, l = rs.count("W"), rs.count("T"), rs.count("L")
        return {"rounds": len(rs), "win": round(w / n, 4), "tie": round(t / n, 4),
                "loss": round(l / n, 4), "decisive_win": round(w / max(w + l, 1), 4)}
    all_ = "".join(lines)
    late = "".join(x[30:] for x in lines)
    first30 = "".join(x[:30] for x in lines)
    return {"all": part(all_), "after30": part(late), "first30": part(first30)}
