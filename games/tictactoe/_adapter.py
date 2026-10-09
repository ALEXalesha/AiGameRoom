"""Окно TicTacToeAi как виджет оболочки.

- MainWindow встаёт внутрь вкладки (флаг Widget вместо отдельного окна);
- данные игрока - в ctx.data_dir: paths.data_dir копии подменяется на неё;
- тема и громкость берутся из ctx, тема меняется на лету по ctx.changed, а сменённые в
  настройках игры уходят в ctx;
- кнопки «Выход» во вкладке нет: игру закрывает крестик вкладки;
- язык: игра только по-русски (GAME_INFO["langs"]);
- pause/resume/shutdown: ход сети ждёт в QTimer.singleShot с номером партии (token);
  увеличенный token отменяет его, resume заново запускает ход, если он за сетью.
"""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget

from games.tictactoe import paths


class TicTacToeWidget(QWidget):
    def __init__(self, ctx):
        super().__init__()
        self.ctx = ctx
        paths.data_dir = lambda: ctx.data_dir
        from games.tictactoe.app.app import MainWindow
        self.inner = MainWindow()
        self.inner.setWindowFlags(Qt.WindowType.Widget)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.inner)
        # «Выход» закрыл бы MainWindow внутри вкладки и оставил её пустой; выходят крестиком вкладки
        self.inner.menu.quit_button.hide()
        if self.inner.settings.theme != ctx.theme:
            self.inner.change_setting("theme", ctx.theme)
        if self.inner.settings.volume != ctx.sound.volume:
            self.inner.change_setting("volume", ctx.sound.volume)
        ctx.changed.connect(self.on_ctx_changed)
        # тему и громкость, сменённые в настройках самой игры, - в ctx: оболочка разнесёт их
        own = self.inner.change_setting

        def change_setting(name, value):
            own(name, value)
            if name == "theme":
                ctx.set_theme(value)
            elif name == "volume":
                ctx.set_volume(value)
        self.inner.change_setting = change_setting

    def minimumSizeHint(self):
        return self.inner.minimumSize()

    def on_ctx_changed(self, what):
        if what == "theme" and self.inner.settings.theme != self.ctx.theme:
            self.inner.change_setting("theme", self.ctx.theme)

    def pause(self):
        self.inner.game.token += 1

    def resume(self):
        game = self.inner.game
        if game.session is not None and self.inner.current_page() == "game":
            game.after_change()

    def shutdown(self):
        self.inner.game.token += 1
        self.inner.settings.save(self.inner.settings_path)
        return True
