from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QWidget


class MeasurementCanvas(QWidget):
    """Displays an image and lets the user click two points to measure a distance."""

    measurement_completed = pyqtSignal(float, float, float, float)  # x1, y1, x2, y2 (image coords)
    mouse_moved = pyqtSignal(float, float)

    POINT_COLOR = QColor(37, 99, 235)
    PENDING_COLOR = QColor(255, 140, 0)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._zoom = 1.0
        self._pending_point: tuple[float, float] | None = None
        self._measurements: list[tuple[float, float, float, float]] = []
        self.setMinimumSize(600, 500)
        self.setMouseTracking(True)

    # ── public API ────────────────────────────────────────────

    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def set_image(self, path: str):
        self._pixmap = QPixmap(path)
        self._pending_point = None
        self._measurements = []
        self.zoom_fit()

    def remove_measurement(self, index: int):
        if 0 <= index < len(self._measurements):
            self._measurements.pop(index)
            self.update()

    def clear_measurements(self):
        self._measurements = []
        self._pending_point = None
        self.update()

    def zoom_in(self):
        self._set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        self._set_zoom(self._zoom * 0.8)

    def zoom_fit(self):
        if not self.has_image():
            return
        iw, ih = self._pixmap.width(), self._pixmap.height()
        self._set_zoom(min(self.width() / iw, self.height() / ih))

    # ── coordinate helpers ────────────────────────────────────

    def _origin(self) -> tuple[float, float]:
        iw, ih = self._pixmap.width(), self._pixmap.height()
        x0 = (self.width() - iw * self._zoom) / 2
        y0 = (self.height() - ih * self._zoom) / 2
        return x0, y0

    def _to_image_coords(self, pos) -> tuple[float, float]:
        x0, y0 = self._origin()
        x = (pos.x() - x0) / self._zoom
        y = (pos.y() - y0) / self._zoom
        iw, ih = self._pixmap.width(), self._pixmap.height()
        return max(0.0, min(x, iw)), max(0.0, min(y, ih))

    def _set_zoom(self, zoom: float):
        self._zoom = max(0.05, min(zoom, 10.0))
        self.update()

    # ── paint ─────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        if not self.has_image():
            painter.setPen(QPen(Qt.GlobalColor.gray))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Load an image to begin measuring")
            return

        x0, y0 = self._origin()
        scaled = self._pixmap.scaled(
            int(self._pixmap.width() * self._zoom),
            int(self._pixmap.height() * self._zoom),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        painter.drawPixmap(int(x0), int(y0), scaled)

        painter.setPen(QPen(self.POINT_COLOR, 2))
        painter.setBrush(QBrush(self.POINT_COLOR))
        for x1, y1, x2, y2 in self._measurements:
            self._draw_measurement(painter, x0, y0, x1, y1, x2, y2)

        if self._pending_point is not None:
            painter.setPen(QPen(self.PENDING_COLOR, 2))
            painter.setBrush(QBrush(self.PENDING_COLOR))
            self._draw_point(painter, x0, y0, *self._pending_point)

    def _draw_point(self, painter, x0, y0, x, y):
        painter.drawEllipse(QPointF(x0 + x * self._zoom, y0 + y * self._zoom), 4, 4)

    def _draw_measurement(self, painter, x0, y0, x1, y1, x2, y2):
        self._draw_point(painter, x0, y0, x1, y1)
        self._draw_point(painter, x0, y0, x2, y2)
        painter.drawLine(
            QPointF(x0 + x1 * self._zoom, y0 + y1 * self._zoom),
            QPointF(x0 + x2 * self._zoom, y0 + y2 * self._zoom),
        )

    # ── mouse ─────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() != Qt.MouseButton.LeftButton or not self.has_image():
            return
        x, y = self._to_image_coords(event.pos())
        if self._pending_point is None:
            self._pending_point = (x, y)
        else:
            x1, y1 = self._pending_point
            self._pending_point = None
            self._measurements.append((x1, y1, x, y))
            self.measurement_completed.emit(x1, y1, x, y)
        self.update()

    def mouseMoveEvent(self, event):
        if self.has_image():
            x, y = self._to_image_coords(event.pos())
            self.mouse_moved.emit(x, y)
