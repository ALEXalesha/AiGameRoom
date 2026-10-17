"""Раскладка экрана: снимок раскладки кода (учитель и запасной вариант) и применение раскладки
сети-дизайнера к настоящим виджетам.

Прямоугольник элемента - (x, y, w, h) в целых пикселях в координатах экрана. В режиме ИИ
раскладки экрана из design_layouts() выключены (QLayout.setEnabled(False)), и элементы стоят
там, куда их поставил apply(); внутри элементов (блоки панели, строки настроек, прокрутка
статистики) работают их собственные раскладки Qt.
"""
from PySide6.QtCore import QPoint


def use_code(screen):
    """Вернуть экрану раскладку кода: включить раскладки и пересчитать сверху вниз."""
    for lay in screen.design_layouts():
        lay.setEnabled(True)
        lay.invalidate()
        lay.activate()


def capture(screen):
    """Раскладка кода экрана при нынешнем размере, ручках и видимости: {имя: (x, y, w, h)}.
    Скрытые элементы (isHidden) в снимок не попадают."""
    use_code(screen)
    out = {}
    for name, widget, _parent in screen.elements():
        if widget.isHidden():
            continue
        p = widget.mapTo(screen, QPoint(0, 0))
        out[name] = (p.x(), p.y(), widget.width(), widget.height())
    return out


def apply(screen, rects):
    """Поставить элементы по прямоугольникам сети (координаты экрана -> координаты родителя)."""
    for lay in screen.design_layouts():
        lay.setEnabled(False)
    for name, widget, parent in screen.elements():
        if name not in rects or widget.isHidden():
            continue
        x, y, w, h = rects[name]
        if parent is not None:
            px, py = rects[parent][:2]
            x, y = x - px, y - py
        widget.setGeometry(int(x), int(y), int(w), int(h))


def placed(screen):
    """Где элементы стоят сейчас (координаты экрана) - для проверок."""
    out = {}
    for name, widget, _parent in screen.elements():
        if not widget.isHidden():
            p = widget.mapTo(screen, QPoint(0, 0))
            out[name] = (p.x(), p.y(), widget.width(), widget.height())
    return out


def ai_mode(screen):
    """True - раскладки экрана выключены и элементы ставит сеть."""
    return not screen.layout().isEnabled()


# Обычные окна: развёрнутые на мониторах 1366x768, 1920x1080, 2560x1440 и 4K (минус панель
# задач) - их сеть-дизайнер должна знать особенно хорошо.
COMMON_SIZES = ((1366, 728), (1920, 1040), (2560, 1400), (3840, 2120), (1600, 900), (1280, 1000))


def sample_sizes(rng, n):
    """Размеры окна для обучения и проверок: 10 % минимальных 820x600, 10 % обычных 1040x720,
    10 % развёрнутых на обычных мониторах, остальные равномерно 820..3840 x 600..2160.
    17.10 обучение до 2560x1440 давало мусор на 4K и половину запасных вариантов на 2560x1440."""
    out = []
    for _ in range(n):
        u = rng.random()
        if u < 0.1:
            out.append((820, 600))
        elif u < 0.2:
            out.append((1040, 720))
        elif u < 0.3:
            out.append(COMMON_SIZES[int(rng.integers(len(COMMON_SIZES)))])
        else:
            out.append((int(rng.integers(820, 3841)), int(rng.integers(600, 2161))))
    return out
