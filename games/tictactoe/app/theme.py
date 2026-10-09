"""Две темы - тёмная и светлая: цвета для рисования поля и таблица стилей QSS."""

PALETTES = {
    "dark": {
        "bg": "#13151b", "surface": "#1c1f28", "surface2": "#252a36", "tile": "#222633",
        "tile_hover": "#2c3242", "border": "#313748", "text": "#e9ebf1", "muted": "#8f97aa",
        "x": "#5ab0ff", "o": "#ff7b93", "accent": "#5b7cff", "accent_text": "#ffffff",
        "win": "#ffd166", "good": "#3ecf8e", "bad": "#ff5d6c", "grid": "#2a2f3d",
    },
    "light": {
        "bg": "#f3f4f8", "surface": "#ffffff", "surface2": "#eceff5", "tile": "#f1f3f8",
        "tile_hover": "#e3e8f3", "border": "#d8dce6", "text": "#1b1e27", "muted": "#626a7c",
        "x": "#2a6de0", "o": "#e0405c", "accent": "#4a63e8", "accent_text": "#ffffff",
        "win": "#f0a500", "good": "#1d9c69", "bad": "#d8404f", "grid": "#e1e5ee",
    },
}

THEME_NAMES = {"dark": "Тёмная", "light": "Светлая"}


def palette(name):
    return PALETTES.get(name, PALETTES["dark"])


def qss(name):
    p = palette(name)
    return f"""
* {{
    font-family: "Segoe UI", "Noto Sans", sans-serif;
    font-size: 14px;
    color: {p['text']};
}}
QMainWindow, QWidget#page, QScrollArea, QScrollArea > QWidget > QWidget#page {{
    background: {p['bg']};
}}
QScrollArea {{ border: none; }}
QLabel, QCheckBox, QRadioButton {{ background: transparent; }}
QLabel#title {{ font-size: 40px; font-weight: 700; }}
QLabel#heading {{ font-size: 26px; font-weight: 700; }}
QLabel#section {{ font-size: 16px; font-weight: 600; }}
QLabel#muted, QLabel#hint {{ color: {p['muted']}; }}
QLabel#hint {{ font-size: 12px; }}
QLabel#status {{ font-size: 22px; font-weight: 700; }}
QLabel#statusWin {{ font-size: 22px; font-weight: 700; color: {p['good']}; }}
QLabel#statusLoss {{ font-size: 22px; font-weight: 700; color: {p['bad']}; }}
QLabel#statusDraw {{ font-size: 22px; font-weight: 700; color: {p['win']}; }}
QLabel#bigNumber {{ font-size: 28px; font-weight: 700; }}
QFrame#card {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 14px;
}}
QPushButton {{
    background: {p['surface2']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 9px 18px;
}}
QPushButton:hover {{ border-color: {p['accent']}; }}
QPushButton:pressed {{ background: {p['tile_hover']}; }}
QPushButton:focus {{ outline: none; }}
QPushButton#primary {{
    background: {p['accent']};
    color: {p['accent_text']};
    border: 1px solid {p['accent']};
    font-weight: 600;
}}
QPushButton#primary:hover {{ background: {p['x']}; border-color: {p['x']}; }}
QPushButton#menu {{
    font-size: 17px;
    padding: 13px 20px;
    min-width: 240px;
}}
QPushButton#menuPrimary {{
    font-size: 17px;
    font-weight: 600;
    padding: 13px 20px;
    min-width: 240px;
    background: {p['accent']};
    color: {p['accent_text']};
    border: 1px solid {p['accent']};
}}
QPushButton#menuPrimary:hover {{ background: {p['x']}; border-color: {p['x']}; }}
QPushButton#seg {{
    border-radius: 8px;
    padding: 7px 10px;
    background: {p['surface2']};
}}
QPushButton#seg:checked {{
    background: {p['accent']};
    color: {p['accent_text']};
    border-color: {p['accent']};
    font-weight: 600;
}}
QComboBox {{
    background: {p['surface2']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 10px;
    min-width: 150px;
}}
QComboBox:hover {{ border-color: {p['accent']}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    selection-background-color: {p['accent']};
    selection-color: {p['accent_text']};
}}
QSlider::groove:horizontal {{
    height: 6px;
    background: {p['surface2']};
    border-radius: 3px;
}}
QSlider::sub-page:horizontal {{
    background: {p['accent']};
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {p['text']};
    width: 16px;
    height: 16px;
    margin: -6px 0;
    border-radius: 8px;
}}
QCheckBox {{ spacing: 10px; }}
QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1px solid {p['border']};
    background: {p['surface2']};
}}
QCheckBox::indicator:checked {{
    background: {p['accent']};
    border-color: {p['accent']};
    image: none;
}}
QTableWidget {{
    background: {p['surface']};
    border: none;
    gridline-color: {p['grid']};
    selection-background-color: {p['surface2']};
    selection-color: {p['text']};
}}
QTableWidget::item {{ padding: 4px 8px; }}
QHeaderView::section {{
    background: {p['surface']};
    color: {p['muted']};
    border: none;
    border-bottom: 1px solid {p['border']};
    padding: 6px 8px;
    font-weight: 600;
}}
QTableCornerButton::section {{ background: {p['surface']}; border: none; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: {p['border']};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QToolTip {{
    background: {p['surface']};
    color: {p['text']};
    border: 1px solid {p['border']};
}}
"""
