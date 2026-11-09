"""Small dependency-free charts drawn with QPainter."""
from __future__ import annotations

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

OK_COLOR = QColor("#2e9e4f")
NG_COLOR = QColor("#d93636")
ERROR_COLOR = QColor("#d9a21b")


def _nice_max(value: float) -> float:
    if value <= 0:
        return 1.0
    step = 10 ** (len(str(int(value))) - 1)
    for mult in (1, 2, 5, 10):
        if value <= step * mult:
            return float(step * mult)
    return float(step * 10)


class StackedBarChart(QWidget):
    """Vertical stacked bars: one bar per category, one segment per series."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categories: list[str] = []
        self._series: list[tuple[str, QColor, list[float]]] = []
        self._empty_text = "No data for this period"
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, categories: list[str], series: list[tuple[str, QColor, list[float]]]):
        self._categories, self._series = list(categories), list(series)
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        text_color = self.palette().text().color()
        fm = QFontMetrics(self.font())
        w, h = self.width(), self.height()

        # legend
        x = 8
        for name, color, _vals in self._series:
            p.fillRect(QRectF(x, 6, 10, 10), color)
            p.setPen(text_color)
            p.drawText(x + 14, 16, name)
            x += 14 + fm.horizontalAdvance(name) + 16

        if not self._categories or not any(sum(v) for v in zip(*[s[2] for s in self._series])):
            p.setPen(text_color)
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_text)
            return

        totals = [sum(vals[i] for _n, _c, vals in self._series) for i in range(len(self._categories))]
        top = _nice_max(max(totals))
        left, right, ctop, bottom = 44, 12, 28, 34
        plot = QRectF(left, ctop, max(10, w - left - right), max(10, h - ctop - bottom))

        grid = QColor(text_color)
        grid.setAlpha(50)
        for i in range(5):
            y = plot.bottom() - plot.height() * i / 4
            p.setPen(QPen(grid, 1))
            p.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            p.setPen(text_color)
            p.drawText(QRectF(0, y - 8, left - 6, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       f"{top * i / 4:g}")

        n = len(self._categories)
        slot = plot.width() / n
        bar_w = min(48.0, slot * 0.7)
        label_every = max(1, int(fm.horizontalAdvance("00-00") * 1.4 // slot) + 1)
        for i, cat in enumerate(self._categories):
            bx = plot.left() + slot * i + (slot - bar_w) / 2
            y = plot.bottom()
            for _name, color, vals in self._series:
                seg = plot.height() * vals[i] / top
                if seg > 0:
                    p.fillRect(QRectF(bx, y - seg, bar_w, seg), color)
                    y -= seg
            if i % label_every == 0:
                p.setPen(text_color)
                p.drawText(QRectF(bx - slot / 2 + bar_w / 2, plot.bottom() + 4, slot, 16),
                           Qt.AlignmentFlag.AlignCenter, cat[5:] if len(cat) == 10 else cat)


class HBarChart(QWidget):
    """Horizontal bars with a label on the left and a value on the right."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._rows: list[tuple[str, float, str]] = []
        self._color = NG_COLOR
        self._maximum = 100.0
        self.setMinimumHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def set_data(self, rows: list[tuple[str, float, str]], maximum: float = 100.0, color: QColor = NG_COLOR):
        """rows: (label, value, value_text)."""
        self._rows, self._maximum, self._color = list(rows), max(maximum, 1e-9), color
        self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        text_color = self.palette().text().color()
        p.setPen(text_color)
        if not self._rows:
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No data for this period")
            return
        fm = QFontMetrics(self.font())
        label_w = min(180, max(fm.horizontalAdvance(r[0]) for r in self._rows) + 8)
        value_w = max(fm.horizontalAdvance(r[2]) for r in self._rows) + 8
        row_h = min(30.0, (self.height() - 8) / len(self._rows))
        track = QColor(text_color)
        track.setAlpha(25)
        for i, (label, value, text) in enumerate(self._rows):
            y = 4 + i * row_h
            bar_x, bar_w = label_w, max(10, self.width() - label_w - value_w - 8)
            p.setPen(text_color)
            p.drawText(QRectF(0, y, label_w - 6, row_h), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                       fm.elidedText(label, Qt.TextElideMode.ElideRight, int(label_w - 8)))
            p.fillRect(QRectF(bar_x, y + 4, bar_w, row_h - 8), track)
            p.fillRect(QRectF(bar_x, y + 4, bar_w * min(1.0, value / self._maximum), row_h - 8), self._color)
            p.drawText(QRectF(bar_x + bar_w + 6, y, value_w, row_h), Qt.AlignmentFlag.AlignVCenter, text)
