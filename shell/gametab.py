"""Вкладка игры: виджет create_widget(ctx) и его жизнь в оболочке.

Протокол (docs/games.md), все методы виджета необязательные:
- pause() / resume() - вкладку скрыли (переключились, свернули окно) / показали снова.
  Нет их - оболочка сама останавливает работающие QTimer и анимации виджета и запускает
  их обратно при возврате;
- shutdown() - вкладку закрыли: остановить потоки за 2 секунды (контракт). После него
  оболочка всё равно гасит таймеры виджета, затем удаляет его.

Ошибка в игре не роняет оболочку: она записывается в problems окна.
"""
import time

from PySide6.QtCore import QAbstractAnimation, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget

SHUTDOWN_LIMIT = 2.0


class GameTab(QWidget):
    def __init__(self, entry, ctx, report):
        super().__init__()
        self.entry = entry
        self.ctx = ctx
        self.report = report          # report(текст) - в журнал проблем окна
        self.paused = False
        self.closed = False
        self.shutdown_seconds = None
        self._timers = []
        self._animations = []
        self.game = entry.module.create_widget(ctx)
        if not isinstance(self.game, QWidget):
            raise TypeError(f"create_widget вернула {type(self.game).__name__}, а не QWidget")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.game)

    def _call(self, name):
        hook = getattr(self.game, name, None)
        if not callable(hook):
            return False, None
        try:
            return True, hook()
        except Exception as e:  # noqa: BLE001
            self.report(f"{self.entry.id}.{name}(): {type(e).__name__}: {e}")
            return True, None

    def pause(self):
        if self.paused or self.closed:
            return
        self.paused = True
        has, _ = self._call("pause")
        if not has:
            self._timers = [t for t in self.game.findChildren(QTimer) if t.isActive()]
            for t in self._timers:
                t.stop()
            self._animations = [a for a in self.game.findChildren(QAbstractAnimation)
                                if a.state() == QAbstractAnimation.State.Running]
            for a in self._animations:
                a.pause()

    def resume(self):
        if not self.paused or self.closed:
            return
        self.paused = False
        has, _ = self._call("resume")
        if not has:
            for t in self._timers:
                t.start()
            for a in self._animations:
                if a.state() == QAbstractAnimation.State.Paused:
                    a.resume()
        self._timers, self._animations = [], []

    def shutdown(self):
        """Остановить игру. Вернуть секунды на shutdown() игры."""
        if self.closed:
            return self.shutdown_seconds
        self.closed = True
        started = time.perf_counter()
        has, result = self._call("shutdown")
        self.shutdown_seconds = time.perf_counter() - started
        if has and result is False:
            self.report(f"{self.entry.id}.shutdown(): потоки не остановились")
        if self.shutdown_seconds > SHUTDOWN_LIMIT:
            self.report(f"{self.entry.id}.shutdown(): {self.shutdown_seconds:.1f} с - дольше {SHUTDOWN_LIMIT:.0f} с")
        for t in self.game.findChildren(QTimer):
            t.stop()
        for a in self.game.findChildren(QAbstractAnimation):
            a.stop()
        self._timers, self._animations = [], []
        return self.shutdown_seconds
