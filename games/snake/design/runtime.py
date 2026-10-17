"""Сети-оформители в игре: шум запуска, раскладка экранов сетью-дизайнером, тайлы поля сетью-
художником, законы, пересэмплирование и запасной вариант кода.

- Шум запуска z берётся случайно при создании окна: каждый запуск окно почти то же, но с
  отличиями. Ручки кода (поля, промежутки) ставятся экранам по тому же шуму - так у элементов
  внутри (блоки панели, строки настроек) те же отступы, что видел дизайнер при обучении.
- Раскладка экрана: сеть -> законы (game/design/laws.py) -> до RESAMPLES новых шумов полей и
  промежутков -> раскладка кода. Считается раз на (экран, размер, тема, язык, видимость).
- Тайлы поля: набор на палитру и шум партии, законы против кодовых тайлов того же шума, до
  RESAMPLES новых шумов, затем кодовый художник. Ключ вне набора (разорванная змейка) - сеть
  с проверкой отличия, иначе кодовый тайл.
- Всё, что сработало не по-сетевому, тихо пишется в журнал (game/design/journal.py).
"""
import numpy as np

from games.snake.design import layout as L
from games.snake.design.knobs import FONT_LEVELS, Z_DIM, code_style, knobs, sample_z
from games.snake.design.laws import check_layout, check_style, check_tiles
from games.snake.design.tiles import CodeTiles, code_tiles, common_keys, group

RESAMPLES = 3
LIMIT = 0.04          # порог отличия тайла, если в паспорте художника его нет
CACHE = 256
MIN_SIZE = (820, 600)   # как game/ui/widget.MIN_WIDTH/MIN_HEIGHT (тест сверяет). Меньше бывает
                        # только до первой раскладки окна (страницы стопки 640x480) - там код


class AiTiles:
    """Источник тайлов для Board: сеть-художник с законами и запасным кодом."""

    def __init__(self, painter, journal, rng, limit=LIMIT, z=None):
        self.painter = painter
        self.journal = journal
        self.rng = rng
        self.limit = float(limit)
        self.z = sample_z(rng) if z is None else np.asarray(z, np.float64)
        self.version = 0
        self._sets = {}         # палитра -> {ключ: тайл}
        self._z_of = {}         # палитра -> шум, которым нарисован набор
        self.code = {}          # палитра -> True, если набор кодовый (запасной)

    def new_match(self):
        """Новая партия - новая «рука» художника."""
        self.z = sample_z(self.rng)
        self._sets.clear()
        self._z_of.clear()
        self.code.clear()
        self.version += 1

    def _make_set(self, palette):
        keys = common_keys()
        kinds = [group(k) for k in keys]
        z = self.z
        why = ""
        for attempt in range(1 + RESAMPLES):
            if attempt:
                z = sample_z(self.rng)
                self.journal.count("tile_resamples")
            try:
                drawn = self.painter.draw(keys, palette, z)
                bad = check_tiles(drawn, code_tiles(keys, palette, z), kinds, self.limit)
            except Exception as err:  # noqa: BLE001 - сбой сети - запасной вариант, не падение
                bad = [f"сбой сети: {err}"]
            if not bad:
                self.journal.count("tile_sets")
                self._z_of[palette] = z
                self.code[palette] = False
                return dict(zip(keys.tolist(), drawn))
            why = bad[0]
        self.journal.count("tile_fallbacks")
        self.journal.note(f"поле: палитра {palette}", why)
        self._z_of[palette] = self.z
        self.code[palette] = True
        return dict(zip(keys.tolist(), code_tiles(keys, palette, self.z)))

    def tiles(self, palette, keys):
        s = self._sets.get(palette)
        if s is None:
            s = self._sets[palette] = self._make_set(palette)
        keys = [int(k) for k in np.asarray(keys).reshape(-1)]
        missing = [k for k in keys if k not in s]
        if missing:
            z = self._z_of[palette]
            code = code_tiles(missing, palette, z)
            drawn = code
            if not self.code[palette]:
                try:
                    drawn = self.painter.draw(missing, palette, z)
                except Exception:  # noqa: BLE001
                    drawn = code
            for k, d, c in zip(missing, drawn, code):
                ok = np.abs(d.astype(np.float32) - c).mean() / 255 <= self.limit
                if not ok:
                    self.journal.count("tile_misses")
                s[k] = d if ok else c
        return {k: s[k] for k in keys}


class AiDesign:
    """Сеть-дизайнер и сеть-художник окна. designer/painter = None - их работа идёт кодом."""

    def __init__(self, designer, painter, journal, rng=None, z=None, limit=LIMIT):
        self.rng = np.random.default_rng() if rng is None else rng
        self.designer = designer
        self.journal = journal
        self.z = sample_z(self.rng) if z is None else np.asarray(z, np.float64).reshape(Z_DIM)
        self.z[2] = min(FONT_LEVELS, key=lambda v: abs(v - self.z[2]))     # шрифт - один из пяти
        self.theme, self.lang = "dark", "ru"
        self.tiles = AiTiles(painter, journal, self.rng, limit) if painter is not None else CodeTiles(self.z)
        self._cache = {}        # ключ раскладки -> (прямоугольники или None, шум)
        self._busy = False
        self.last = {}          # экран -> {"source": "net"/"code", "deviation": px, "problems": [...]}

    # --- стиль --------------------------------------------------------------------------

    def style(self, theme, lang):
        """Стиль окна: ответ сети, если читается (контраст), иначе стиль кода по тому же шуму."""
        from games.snake.ui import theme as T
        self.theme, self.lang = theme, lang       # раскладки в кэше - по теме и языку, чистить не надо
        code = code_style(T.tokens(theme), self.z)
        if self.designer is None:
            return code
        try:
            style = self.designer.style(theme, lang, self.z)
            bad = check_style(T.tokens(theme, style))
            if not (0.9 <= style["font"] <= 1.1 and 4 <= style["radius"] <= 16):
                bad.append(f"шрифт {style['font']:.2f} или скругление {style['radius']:.1f} вне пределов")
        except Exception as err:  # noqa: BLE001
            bad = [f"сбой сети: {err}"]
        if bad:
            self.journal.note("окно: стиль", bad[0])
            return code
        return style

    def knobs(self):
        return knobs(self.z)

    # --- раскладка ---------------------------------------------------------------------

    def layout(self, screen):
        if self._busy or screen.width() <= 0 or not screen.NAME:
            return
        if screen.width() < MIN_SIZE[0] or screen.height() < MIN_SIZE[1]:
            screen.set_knobs(self.knobs())
            L.use_code(screen)
            return
        key = (screen.NAME, screen.width(), screen.height(), self.theme, self.lang, screen.flags())
        hit = self._cache.get(key)
        self._busy = True
        try:
            if hit is not None:
                rects, z = hit
                screen.set_knobs(knobs(z))
                if rects is None:
                    L.use_code(screen)
                    return
                # тексты и шрифты могли смениться с прошлого раза - законы ещё раз (~1 мс)
                if not check_layout(screen, rects):
                    L.apply(screen, rects)
                    return
            if len(self._cache) > CACHE:
                self._cache.clear()
            rects, z = self._decide(screen)
            self._cache[key] = (rects, z)
        finally:
            self._busy = False

    def _decide(self, screen):
        name = screen.NAME
        if self.designer is None:
            screen.set_knobs(self.knobs())
            L.use_code(screen)
            self.last[name] = {"source": "code", "deviation": None, "problems": ["нет сети-дизайнера"]}
            return None, self.z
        flags = screen.flags()
        problems = []
        z = self.z
        for attempt in range(1 + RESAMPLES):
            if attempt:
                z = self.z.copy()
                z[[0, 1]] = self.rng.uniform(-1, 1, 2)      # поля и промежутки; шрифт тот же
                self.journal.count("layout_resamples")
            screen.set_knobs(knobs(z))
            try:
                rects = self.designer.layout(name, screen.width(), screen.height(), self.theme, self.lang,
                                             flags, z)
                problems = check_layout(screen, rects)
            except Exception as err:  # noqa: BLE001
                rects, problems = None, [f"сбой сети: {err}"]
            if not problems:
                dev = self._deviation(screen, rects, z)
                L.apply(screen, rects)
                self.journal.count("layouts")
                if dev is not None:
                    self.journal.deviation(dev)
                self.last[name] = {"source": "net", "deviation": dev, "problems": []}
                return rects, z
        # запасной вариант - раскладка кода по тому же шуму, а если и ей тесно (окно
        # минимального размера и шрифт шире, чем в offscreen) - раскладка 1.1 без шума
        z = self.z
        screen.set_knobs(knobs(z))
        if check_layout(screen, L.capture(screen)):
            z = np.zeros(Z_DIM)
            screen.set_knobs(knobs(z))
            L.use_code(screen)
        self.journal.count("layout_fallbacks")
        self.journal.note(f"окно: {name} {screen.width()}x{screen.height()}", problems[0])
        self.last[name] = {"source": "code", "deviation": None, "problems": problems}
        return None, z

    def _deviation(self, screen, rects, z):
        """Среднее отличие раскладки сети от раскладки кода без шума (обычное окно 1.1), px."""
        screen.set_knobs(knobs(np.zeros(Z_DIM)))
        code = L.capture(screen)
        screen.set_knobs(knobs(z))
        L.use_code(screen)
        diffs = [np.abs(np.subtract(rects[n], code[n])).mean() for n in code if n in rects]
        return float(np.mean(diffs)) if diffs else None


def from_models(models, journal, rng=None):
    """AiDesign по моделям: нет файла или он битый - эта часть кодом, причина в журнале."""
    designer = painter = None
    limit = LIMIT
    for what in ("designer", "painter"):
        loader = getattr(models, "load_" + what, None)
        if loader is None:
            continue
        try:
            net = loader()
        except Exception as err:  # noqa: BLE001 - игра идёт на коде
            journal.note(f"{'окно' if what == 'designer' else 'поле'}: нет сети", err)
            continue
        if what == "designer":
            designer = net
        else:
            painter = net
            passport = models.load_passport("painter") if hasattr(models, "load_passport") else None
            if isinstance(passport, dict) and isinstance(passport.get("limit"), (int, float)):
                limit = float(passport["limit"])
    return AiDesign(designer, painter, journal, rng=rng, limit=limit)
