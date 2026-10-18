"""Темы виджета - тёмная (как в 1.0) и светлая: QSS и палитра Qt для стиля Fusion.

Тема приходит из ctx (оболочка или окно отдельного запуска) и меняется на лету. Палитра и
QSS ставятся на сам виджет игры, а не на всё приложение: в оболочке рядом живут другие игры.
Цвета поля (Ночь, Океан, Светлая) - отдельная настройка игры, от темы не зависят.
"""
from PySide6.QtGui import QColor, QPalette

THEMES = ("dark", "light")

# 2.1: «террариум» (правило автора 17.10: у каждой игры свой вид меню, настроек и статистики):
# тёмная - ночной террариум (мох и хвоя вместо сине-серого), светлая - сад днём.
TOKENS = {
    "dark": {
        "bg": "#08110d", "card": "#0f1d17", "line": "#1f3b2e", "text": "#e3f1e8", "muted": "#8fae9c",
        "accent": "#36d07f", "accent_hover": "#4ce292", "accent_pressed": "#27b06a", "accent_text": "#04130a",
        "title": "#9ef0b0", "button": "#12241c", "button_border": "#25493a", "button_hover": "#183026",
        "button_hover_border": "#3b6f56", "button_pressed": "#0c1913", "focus": "#4f8f70",
        "groove": "#1d3529", "handle_hover": "#ffffff", "selection": "#1f5a3c", "progress": "#15281f",
        "warn_bg": "#3a2417", "warn_text": "#ffcf9e", "warn_border": "#6b3f22",
        "good": "#5fd08f", "mid": "#e2b340", "bad": "#e5484d", "score_sep": "#4f6b5d",
        "highlighted_text": "#ffffff",
    },
    "light": {
        "bg": "#eef3e6", "card": "#fbfdf7", "line": "#cddcc2", "text": "#18261c", "muted": "#566b5c",
        "accent": "#1f9d5a", "accent_hover": "#25b268", "accent_pressed": "#198a4e", "accent_text": "#ffffff",
        "title": "#17703f", "button": "#f1f6ea", "button_border": "#c3d4b6", "button_hover": "#e4eedb",
        "button_hover_border": "#9fb98f", "button_pressed": "#d6e4ca", "focus": "#7fa087",
        "groove": "#d1dec6", "handle_hover": "#0f1319", "selection": "#bfe6cf", "progress": "#dde8d3",
        "warn_bg": "#fff1e3", "warn_text": "#7a3d0a", "warn_border": "#f0c08f",
        "good": "#1f9d5a", "mid": "#b7860b", "bad": "#d1343a", "score_sep": "#8a9a8d",
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


def _rgba(color, alpha):
    c = color.lstrip("#")
    return f"rgba({int(c[0:2], 16)}, {int(c[2:4], 16)}, {int(c[4:6], 16)}, {alpha})"


def _pt(v, k):
    return f"{v * k:.4g}pt"


def qss(name="dark", style=None, scale=1.0):
    """QSS виджета. style: font - множитель шрифтов, radius - скругление кнопок (карточки +4),
    colors - акцентные цвета. style=None - основной вид без шума. scale - масштаб окна (game/ui/look.scale_for):
    шрифты, поля кнопок и скругления растут вместе с окном (4K без масштаба Windows - не крошечный текст)."""
    t = tokens(name, style)
    k = float(scale)
    f = (float(style["font"]) if style else 1.0) * k
    r = (float(style["radius"]) if style else 10.0) * k

    def px(v):
        return f"{round(v * k)}px"
    rb, rc, rk = f"{r:.3g}px", f"{max(r - 2, 2):.3g}px", f"{r + 4:.3g}px"
    return f"""
QMainWindow, QWidget#gameRoot, QStackedWidget, QWidget#screen {{ background: {t['bg']}; }}
QWidget#scrollBody {{ background: transparent; }}
QWidget {{ color: {t['text']}; font-family: "Segoe UI", "Noto Sans", sans-serif; font-size: {_pt(10.5, f)}; }}
QToolTip {{ background: {t['card']}; color: {t['text']}; border: {px(1)} solid {t['line']}; padding: {px(4)} {px(6)}; }}

QLabel#title {{ font-family: "Candara", "Segoe UI"; font-size: {_pt(40, f)}; font-weight: 700; color: {t['title']}; }}
QLabel#screenTitle {{ font-family: "Candara", "Segoe UI"; font-size: {_pt(22, f)}; font-weight: 700; color: {t['title']}; }}
QLabel#subtitle, QLabel#muted {{ color: {t['muted']}; }}
QLabel#section {{ font-family: "Cascadia Code", "Consolas"; color: {t['accent']}; font-size: {_pt(8.5, f)};
                  font-weight: 600; letter-spacing: {px(1)}; }}
QLabel#big {{ font-family: "Cascadia Code", "Consolas"; font-size: {_pt(28, f)}; font-weight: 700; }}
QLabel#cardValue {{ font-family: "Cascadia Code", "Consolas"; font-size: {_pt(21, f)}; font-weight: 700;
                    color: {t['title']}; }}
QLabel#value {{ font-weight: 600; }}
QLabel#warning {{ background: {t['warn_bg']}; color: {t['warn_text']}; border: {px(1)} solid {t['warn_border']};
                 border-radius: {rb}; padding: {px(10)} {px(14)}; }}
QLabel#overlayTitle {{ font-size: {_pt(26, f)}; font-weight: 700; }}

QFrame#panel, QFrame#card {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {_rgba(t['card'], 236)},
                             stop:1 {_rgba(t['bg'], 220)}); border: {px(1)} solid {t['line']};
                             border-top: {px(2)} solid {t['button_hover_border']}; border-radius: {rk}; }}
QFrame#overlayCard {{ background: {t['card']}; border: {px(1)} solid {t['line']}; border-top: {px(3)} solid {t['accent']};
                     border-radius: {rk}; }}
QFrame#panel QLabel, QFrame#card QLabel, QFrame#overlayCard QLabel {{ background: transparent;
                                                                    border: none; }}
QFrame#separator {{ background: {t['line']}; border: none; max-height: {px(1)}; min-height: {px(1)}; }}

QPushButton {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['button_hover']}, stop:1 {t['button']});
              border: {px(1)} solid {t['button_border']}; border-radius: {rb};
              padding: {px(10)} {px(18)}; font-size: {_pt(11, f)}; }}
QPushButton:hover {{ background: {t['button_hover']}; border-color: {t['button_hover_border']}; }}
QPushButton:pressed {{ background: {t['button_pressed']}; }}
QPushButton:focus {{ border-color: {t['focus']}; }}
QPushButton#primary {{ background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {t['accent_hover']},
                      stop:1 {t['accent_pressed']}); color: {t['accent_text']}; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {t['accent_hover']}; }}
QPushButton#primary:pressed {{ background: {t['accent_pressed']}; }}
QPushButton#flat {{ background: transparent; border: none; color: {t['muted']}; padding: {px(6)} {px(10)}; }}
QPushButton#flat:hover {{ color: {t['text']}; }}

QSlider::groove:horizontal {{ height: {px(6)}; background: {t['groove']}; border-radius: {px(3)}; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: {px(3)}; }}
QSlider::handle:horizontal {{ width: {px(18)}; height: {px(18)}; margin: -{px(7)} 0; border-radius: {px(9)};
                             background: {t['text']}; }}
QSlider::handle:horizontal:hover {{ background: {t['handle_hover']}; }}

QComboBox {{ background: {t['button']}; border: {px(1)} solid {t['button_border']}; border-radius: {rc};
            padding: {px(6)} {px(12)}; min-width: {px(150)}; }}
QComboBox:hover {{ border-color: {t['button_hover_border']}; }}
QComboBox::drop-down {{ border: none; width: {px(24)}; }}
QComboBox QAbstractItemView {{ background: {t['button']}; border: {px(1)} solid {t['button_border']};
                              selection-background-color: {t['selection']}; outline: none; }}

QCheckBox {{ spacing: {px(10)}; }}
QCheckBox::indicator {{ width: {px(16)}; height: {px(16)}; border-radius: {px(6)}; border: {px(2)} solid {t['button_hover_border']};
                       background: {t['button']}; }}
QCheckBox::indicator:checked {{ background: {t['accent']}; border-color: {t['accent']}; image: none; }}

QProgressBar {{ background: {t['progress']}; border: none; border-radius: {px(5)}; max-height: {px(10)};
               min-height: {px(10)}; }}
QProgressBar::chunk {{ background: {t['accent']}; border-radius: {px(5)}; }}
QProgressBar[level="mid"]::chunk {{ background: {t['mid']}; }}
QProgressBar[level="bad"]::chunk {{ background: {t['bad']}; }}

QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: {px(10)}; margin: {px(2)}; }}
QScrollBar::handle:vertical {{ background: {t['button_border']}; border-radius: {px(4)}; min-height: {px(30)}; }}
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
