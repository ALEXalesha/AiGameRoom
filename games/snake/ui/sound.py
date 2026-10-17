"""Звуки игры: синтез numpy (чистые функции, int16 моно) и проигрывание через QtMultimedia.

Без звуковой карты или без QtMultimedia игра не падает - просто молчит.
"""
import atexit
import os
import shutil
import tempfile
import wave

import numpy as np

RATE = 22050
EAT_MS = 90
CRASH_MS = 280
BEEP_MS = 120
WIN_MS = 560
LOSE_MS = 600
FADE_MS = 6          # плавный край ноты - без щелчка
PEAK = 0.6


def _samples(ms, rate=RATE):
    return int(rate * ms / 1000)


def _pcm(wave_, peak=PEAK):
    top = np.abs(wave_).max()
    if top > 0:
        wave_ = wave_ * (peak / top)
    return (np.clip(wave_, -1.0, 1.0) * 32767.0).astype(np.int16)


def _edges(n, rate=RATE, fade_ms=FADE_MS):
    """Огибающая: короткий подъём и спуск к нулю на краях."""
    env = np.ones(n)
    k = max(1, min(n // 2, _samples(fade_ms, rate)))
    ramp = np.linspace(0.0, 1.0, k)
    env[:k] *= ramp
    env[-k:] *= ramp[::-1]
    return env


def _melody(notes, total_ms, rate=RATE, decay_ms=None, harmonic=0.25):
    """notes - [(частота, мс) или (частота в начале, частота в конце, мс)] подряд.
    Длина ровно total_ms, границы нот считаются по сумме миллисекунд."""
    n = _samples(total_ms, rate)
    out = np.zeros(n)
    spans = [(nt[0], nt[0], nt[1]) if len(nt) == 2 else nt for nt in notes]
    scale = total_ms / sum(s[2] for s in spans)
    start_ms = 0.0
    for i, (f0, f1, ms) in enumerate(spans):
        a = _samples(start_ms * scale, rate)
        start_ms += ms
        b = n if i == len(spans) - 1 else _samples(start_ms * scale, rate)
        m = b - a
        if m <= 0:
            continue
        freq = np.linspace(f0, f1, m)
        phase = 2 * np.pi * np.cumsum(freq) / rate
        tone = np.sin(phase) + harmonic * np.sin(3 * phase) / 3
        env = _edges(m, rate)
        if decay_ms:
            env *= np.exp(-np.arange(m) / rate / (decay_ms / 1000))
        out[a:b] = tone * env
    return out


def eat(pitch=1.0):
    """Еда: два коротких восходящих тона."""
    return _pcm(_melody([(660 * pitch, 40), (990 * pitch, 50)], EAT_MS, decay_ms=60), 0.5)


def eat_net():
    """Еду съела сеть - тот же звук ниже и тише."""
    return _pcm(_melody([(660 * 0.7, 40), (990 * 0.7, 50)], EAT_MS, decay_ms=60,
                        harmonic=0.1), 0.35)


def crash():
    """Столкновение: глухой удар (частота падает) и шум, быстро затухают."""
    n = _samples(CRASH_MS)
    t = np.arange(n) / RATE
    freq = 150 * np.exp(-t / 0.08) + 45
    thump = np.sin(2 * np.pi * np.cumsum(freq) / RATE)
    noise = np.convolve(np.random.default_rng(1).normal(0, 1, n), np.ones(6) / 6, "same")
    body = (0.9 * thump + 0.6 * noise) * np.exp(-t / 0.07)
    return _pcm(body * _edges(n), 0.8)


def beep():
    """Отсчёт 3, 2, 1."""
    return _pcm(_melody([(440, BEEP_MS)], BEEP_MS, harmonic=0.15), 0.45)


def go():
    """Старт после отсчёта - тот же бип, но выше."""
    return _pcm(_melody([(880, BEEP_MS)], BEEP_MS, harmonic=0.15), 0.5)


def win():
    """Победа: арпеджио вверх до-ми-соль-до."""
    return _pcm(_melody([(523, 110), (659, 110), (784, 110), (1047, 230)], WIN_MS,
                        harmonic=0.2))


def lose():
    """Поражение: вниз соль-ми-до, последняя нота сползает."""
    return _pcm(_melody([(392, 150), (330, 150), (262, 200, 300)], LOSE_MS, harmonic=0.3))


SOUNDS = {"eat": eat, "eat_net": eat_net, "crash": crash, "beep": beep, "go": go,
          "win": win, "lose": lose}

# Событие матча -> звук. Остальные события (round_win и т.п.) без звука.
EVENT_SOUND = {"eat0": "eat", "eat1": "eat_net", "crash": "crash", "countdown": "beep",
               "go": "go", "win": "win", "lose": "lose"}


def write_wav(path, samples, rate=RATE):
    path = os.fspath(path)
    with wave.open(path, "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes(np.asarray(samples, np.int16).tobytes())
    return path


class Sounds:
    """Проигрыватель: WAV в папке folder (у игры - в ctx.data_dir; без неё - во временной
    папке, убираемой при выходе), QSoundEffect на каждый звук."""

    def __init__(self, volume=60, enabled=True, folder=None):
        self.effects = {}
        self.volume = volume
        self.folder = folder
        # без экрана (тесты, самопроверка, проверка контракта) - и без звука: QtMultimedia в
        # offscreen держала канал вывода проверки открытым после выхода (10.10.2026)
        if enabled and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            try:
                self._load()
            except Exception:  # noqa: BLE001 - нет QtMultimedia или звука: молчим
                self.effects = {}
        self.set_volume(volume)

    def _load(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtMultimedia import QMediaDevices, QSoundEffect

        if not QMediaDevices.audioOutputs():
            return
        folder = self.folder
        if folder is None:
            folder = tempfile.mkdtemp(prefix="snakeai-sounds-")
            atexit.register(shutil.rmtree, folder, True)
        os.makedirs(folder, exist_ok=True)
        for name, make in SOUNDS.items():
            path = write_wav(os.path.join(folder, name + ".wav"), make())
            effect = QSoundEffect()
            effect.setSource(QUrl.fromLocalFile(path))
            self.effects[name] = effect

    def set_volume(self, volume):
        self.volume = volume
        for effect in self.effects.values():
            try:
                effect.setVolume(max(0.0, min(1.0, volume / 100)))
            except Exception:  # noqa: BLE001
                pass

    def play(self, name):
        effect = self.effects.get(name)
        if effect is None or self.volume <= 0:
            return
        try:
            effect.play()
        except Exception:  # noqa: BLE001 - звук пропал посреди игры
            pass

    def on_event(self, event):
        name = EVENT_SOUND.get(event)
        if name:
            self.play(name)
