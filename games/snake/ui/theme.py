"""Темы виджета - тёмная (как в 1.0) и светлая: QSS и палитра Qt для стиля Fusion.

Тема приходит из ctx (оболочка или окно отдельного запуска) и меняется на лету. Палитра и
QSS ставятся на сам виджет игры, а не на всё приложение: в оболочке рядом живут другие игры.
Цвета поля (Ночь, Океан, Светлая) - отдельная настройка игры, от темы не зависят.
"""
from PySide6.QtGui import QColor, QPalette

THEMES = ("dark", "light")

TOKENS = {
    "dark": {
        "bg": "#0f1319", "card": "#161b23", "line": "#252d3a", "text": "#e6ebf2", "muted": "#8b96a8",
        "accent": "#2fbf71", "accent_hover": "#3fd183", "accent_pressed": "#28a862", "accent_text": "#06110a",
        "title": "#7ee2a8", "button": "#1d2430", "button_border": "#2c3544", "button_hover": "#253042",
        "button_hover_border": "#3d4a5e", "button_pressed": "#161c26", "focus": "#4a5a72",
        "groove": "#2a3342", "handle_hover": "#ffffff", "selection": "#2a5a3f", "progress": "#232b37",
        "warn_bg": "#3a2417", "warn_text": "#ffcf9e", "warn_border": "#6b3f22",
        "good": "#5fd08f", "mid": "#e2b340", "bad": "#e5484d", "score_sep": "#5b6577",
        "highlighted_text": "#ffffff",
    },
    "light": {
        "bg": "#f3f5f8", "card": "#ffffff", "line": "#d9dee6", "text": "#1c2430", "muted": "#5f6b7d",
        "accent": "#1f9d5a", "accent_hover": "#25b268", "accent_pressed": "#198a4e", "accent_text": "#ffffff",
        "title": "#1a8a4c", "button": "#eef1f5", "button_border": "#cfd6e0", "button_hover": "#e3e8ef",
        "button_hover_border": "#b6c0ce", "button_pressed": "#d8dee7", "focus": "#8a9ab2",
        "groove": "#d5dbe4", "handle_hover": "#0f1319", "selection": "#bfe6cf", "progress": "#e1e6ed",
        "warn_bg": "#fff1e3", "warn_text": "#7a3d0a", "warn_border": "#f0c08f",
        "good": "#1f9d5a", "mid": "#b7860b", "bad": "#d1343a", "score_sep": "#8a94a5",
        "highlighted_text": "#0f1319",
    },
}

# прежние имена (тёмная тема) - для кода, которому тема не важна
BG, CARD, LINE, TEXT, MUTED, ACCENT = (TOKENS["dark"][k] for k in ("bg", "card", "line", "text", "muted", "accent"))


def tokens(name, style=None):
    """Цвета темы; style (game/design/knobs.code_style или ответ сети-дизайнера) подменяет
    акцентные цвета."""
    t = dict(TOKENS[name if name in TOKENS else "dark"])
    if style:
        t.update(style.get("colors", {}))
    return t


def _pt(v, k):
    return f"{v * k:.4g}pt"


def qss(name="dark", style=None):
    """QSS виджета. style: font - множитель шрифтов, radius - скругление кнопок (карточки +4),
    colors - акцентные цвета. style=None - оформление 1.1.0."""
    t = tokens(name, style)
    f = float(style["font"]) if style else 1.0
    r = float(style["radius"]) if style else 10.0
    rb, rc, rk = f"{r:.3g}px", f"{max(r - 2, 2):.3g}px", f"{r + 4:.3g}px"
    return f"""
QMainWindow, QWidget#gameRoot, QStackedWidget, QWidget#screen, QWidget#scrollBody {{ background: {t['bg']}; }}
QWidget {{ color: {t['text']}; font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: {_pt(10.5, f)}; }}
QToolTip {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['line']}; padding: 4px 6px; }}

QLabel#title {{ font-size: {_pt(36, f)}; font-weight: 700; color: {t['title']}; }}
QLabel#screenTitle {{ font-size: {_pt(20, f)}; font-weight: 600; }}
QLabel#subtitle, QLabel#muted {{ color: {t['muted']}; }}
QLabel#section {{ color: {t['muted']}; font-size: {_pt(9, f)}; font-weight: 600; letter-spacing: 1px; }}
QLabel#big {{ font-size: {_pt(30, f)}; font-weight: 700; }}
QLabel#cardValue {{ font-size: {_pt(22, f)}; font-weight: 700; }}
QLabel#value {{ font-weight: 600; }}
QLabel#warning {{ background: {t['warn_bg']}; color: {t['warn_text']}; border: 1px solid {t['warn_border']};
                 border-radius: {rb}; padding: 10px 14px; }}
QLabel#overlayTitle {{ font-size: {_pt(26, f)}; font-weight: 700; }}

QFrame#panel, QFrame#card, QFrame#overlayCard {{ background: {t['card']}; border: 1px solid {t['line']};
                                               border-radius: {rk}; }}
QFrame#panel QLabel, QFrame#card QLabel, QFrame#overlayCard QLabel {{ background: transparent;
                                                                    border: none; }}
QFrame#separator {{ background: {t['line']}; border: none; max-height: 1px; min-height: 1px; }}

QPushButton {{ background: {t['button']}; border: 1px solid {t['button_border']}; border-radius: {rb};
              padding: 10px 18px; font-size: {_pt(11, f)}; }}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['button_hover_border']}; }}
QPushButton:pressed {{ background: {t['button_pressed']}; }}
QPushButton:focus {{ border-color: {t['focus']}; }}
QPushButton#primary {{ background: {t['accent']}; color: {t['accent_text']}; border: none; font-weight: 600; }}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary:pressed {{ background: {t['accent_pressed']}; }}
QPushButton#flat {{ background: transparent; border: none; color: {t['muted']}; padding: 6px 10px; }}
QPushButton#flat:hover {{ color: {t['text']}; }}

QSlider::groove:horizontal {{ height: 6px; background: {t['groove']}; border-radius: 3px; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 3px; }}
QSlider::handle:horizontal {{ width: 18px; height: 18px; margin: -7px 0; border-radius: 9px;
                             background: {t['text']}; }}
QSlider::handle:horizontal:hover {{ background: {t['handle_hover']}; }}

QComboBox {{ background: {t['button']}; border: 1px solid {t['button_border']}; border-radius: {rc};
            padding: 6px 12px; min-width: 150px; }}
QComboBox:hover {{ border-color: {t['button_hover_border']}; }}
QComboBox::drop-down {{ border: none; width: 24px; }}
QComboBox QAbstractItemView {{ background: {t['button']}; border: 1px solid {t['button_border']};
                              selection-background-color: {t['selection']}; outline: none; }}

QCheckBox {{ spacing: 10px; }}

QProgressBar {{ background: {t['progress']}; border: none; border-radius: 5px; max-height: 10px;
               min-height: 10px; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: 5px; }}
QProgressBar[level="mid"]::chunk {{ background: {t['mid']}; }}
QProgressBar[level="bad"]::chunk {{ background: {t['bad']}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {t['button_border']}; border-radius: 4px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


QSS = qss("dark")


def palette(name="dark", style=None):
    """Палитра Qt: у стиля Fusion по ней рисуется всё, что не описано в QSS."""
    t = tokens(name, style)
    p = QPalette()
    roles = {
        QPalette.ColorRole.Window: t["bg"], QPalette.ColorRole.WindowText: t["text"],
        QPalette.ColorRole.Base: t["button"], QPalette.ColorRole.AlternateBase: t["card"],
        QPalette.ColorRole.Text: t["text"], QPalette.ColorRole.Button: t["button"],
        QPalette.ColorRole.ButtonText: t["text"], QPalette.ColorRole.Highlight: t["selection"],
        QPalette.ColorRole.HighlightedText: t["highlighted_text"], QPalette.ColorRole.ToolTipBase: t["card"],
        QPalette.ColorRole.ToolTipText: t["text"], QPalette.ColorRole.PlaceholderText: t["muted"],
    }
    for role, color in roles.items():
        p.setColor(role, QColor(color))
    return p


def apply(app, name="dark"):
    """Окно отдельного запуска: стиль Fusion и палитра всего приложения, как в 1.0. В оболочке
    не зовётся - там виджет ставит палитру только себе."""
    app.setStyle("Fusion")
    app.setPalette(palette(name))
