from typing import Optional

import numpy as np
from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QImage, QPainter, QPen
from PyQt6.QtWidgets import QSizePolicy, QWidget

from ..inspection.engine import Roi
from ..utils.qt_image import bgr_to_qimage

_COLORS = {"include": QColor(40, 200, 80), "ignore": QColor(230, 60, 60)}


class RoiCanvas(QWidget):
    """Shows an image and lets the user draw include/ignore rectangles with the mouse.
    Left-drag draws a ROI in the current mode, right-click removes the ROI under the cursor."""
    rois_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._image: Optional[QImage] = None
        self._rois: list[Roi] = []
        self._mode = "include"
        self._drag_start: Optional[QPointF] = None
        self._drag_now: Optional[QPointF] = None
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)

    # ── public API ──
    def set_image(self, img: Optional[np.ndarray]):
        self._image = bgr_to_qimage(img) if img is not None else None
        self.update()

    def set_mode(self, mode: str):
        self._mode = mode

    def set_rois(self, rois: list[Roi]):
        self._rois = list(rois)
        self.update()

    def rois(self) -> list[Roi]:
        return list(self._rois)

    def clear_rois(self):
        if self._rois:
            self._rois.clear()
            self.update()
            self.rois_changed.emit()

    # ── geometry ──
    def _image_rect(self) -> QRectF:
        if self._image is None or self._image.width() == 0:
            return QRectF()
        iw, ih = self._image.width(), self._image.height()
        s = min(self.width() / iw, self.height() / ih)
        w, h = iw * s, ih * s
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _to_norm(self, p: QPointF, r: QRectF) -> tuple[float, float]:
        return (min(1.0, max(0.0, (p.x() - r.x()) / r.width())),
                min(1.0, max(0.0, (p.y() - r.y()) / r.height())))

    def _roi_rect(self, roi: Roi, r: QRectF) -> QRectF:
        return QRectF(r.x() + roi.x * r.width(), r.y() + roi.y * r.height(),
                      roi.w * r.width(), roi.h * r.height())

    # ── events ──
    def paintEvent(self, _):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(30, 30, 30))
        r = self._image_rect()
        if r.isEmpty():
            p.setPen(QColor(160, 160, 160))
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Select or create a reference")
            return
        p.drawImage(r, self._image)
        for roi in self._rois:
            c = _COLORS.get(roi.mode, _COLORS["include"])
            rect = self._roi_rect(roi, r)
            fill = QColor(c)
            fill.setAlpha(55)
            p.fillRect(rect, fill)
            p.setPen(QPen(c, 2))
            p.drawRect(rect)
        if self._drag_start is not None and self._drag_now is not None:
            c = _COLORS[self._mode]
            p.setPen(QPen(c, 2, Qt.PenStyle.DashLine))
            p.drawRect(QRectF(self._drag_start, self._drag_now).normalized().intersected(r))

    def mousePressEvent(self, e):
        r = self._image_rect()
        if r.isEmpty() or not r.contains(e.position()):
            return
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self._drag_now = e.position()
        elif e.button() == Qt.MouseButton.RightButton:
            for roi in reversed(self._rois):
                if self._roi_rect(roi, r).contains(e.position()):
                    self._rois.remove(roi)
                    self.update()
                    self.rois_changed.emit()
                    break

    def mouseMoveEvent(self, e):
        if self._drag_start is not None:
            self._drag_now = e.position()
            self.update()

    def mouseReleaseEvent(self, e):
        if self._drag_start is None or e.button() != Qt.MouseButton.LeftButton:
            return
        r = self._image_rect()
        x0, y0 = self._to_norm(self._drag_start, r)
        x1, y1 = self._to_norm(e.position(), r)
        self._drag_start = self._drag_now = None
        x, y, w, h = min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)
        if w > 0.01 and h > 0.01:
            self._rois.append(Roi(x, y, w, h, self._mode))
            self.rois_changed.emit()
        self.update()
