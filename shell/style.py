"""Стиль оболочки: таблица aikit.theme.qss плюс вкладки, поиск и карточки игр.
aikit не правится под оболочку - дополнения живут здесь."""
from aikit import theme


def qss(name):
    p = theme.palette(name)
    return theme.qss(name) + f"""
QTabWidget::pane {{ border: none; background: {p['bg']}; }}
QTabBar {{ background: {p['bg']}; }}
QTabBar::tab {{
    background: {p['surface']};
    color: {p['muted']};
    border: 1px solid {p['border']};
    border-bottom: none;
    border-top-left-radius: 10px;
    border-top-right-radius: 10px;
    padding: 7px 14px;
    margin-right: 4px;
    min-width: 90px;
}}
QTabBar::tab:selected {{ background: {p['surface2']}; color: {p['text']}; font-weight: 600; }}
QTabBar::tab:hover {{ color: {p['text']}; }}
QLineEdit {{
    background: {p['surface2']};
    border: 1px solid {p['border']};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {p['accent']};
}}
QLineEdit:focus {{ border-color: {p['accent']}; }}
QFrame#gameCard {{
    background: {p['surface']};
    border: 1px solid {p['border']};
    border-radius: 14px;
}}
QFrame#gameCard:hover {{ border-color: {p['accent']}; }}
QFrame#gameCardBroken {{
    background: {p['surface']};
    border: 1px dashed {p['bad']};
    border-radius: 14px;
}}
QLabel#preview {{ background: {p['surface2']}; border-radius: 10px; color: {p['muted']}; }}
QLabel#error {{ color: {p['bad']}; }}
QLabel#cardTitle {{ font-size: 18px; font-weight: 700; }}
"""
