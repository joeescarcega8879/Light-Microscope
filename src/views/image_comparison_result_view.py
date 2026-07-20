import os
import cv2
import numpy as np
from datetime import datetime
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.QtGui import QPixmap, QImage


class ImageComparisonResultView(QWidget):
    view_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._heatmap_pixmap: QPixmap | None = None
        self._diff_pixmap: QPixmap | None = None
        self._contours_pixmap: QPixmap | None = None
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "image_comparison_result_widget.ui")
        uic.loadUi(ui_path, self)
        self.btnSaveResult.clicked.connect(self._save_result)

    def display_diff(self, diff: np.ndarray):
        h, w = diff.shape
        q_image = QImage(diff.data, w, h, w, QImage.Format.Format_Grayscale8)
        self._diff_pixmap = QPixmap.fromImage(q_image)
        self.lblDiff.setPixmap(self._diff_pixmap)

    def display_heatmap(self, heatmap: np.ndarray):
        heatmap_rgb = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
        h, w, ch = heatmap_rgb.shape
        q_image = QImage(heatmap_rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._heatmap_pixmap = QPixmap.fromImage(q_image)
        self.lblHeatmap.setPixmap(self._heatmap_pixmap)

    def display_contours(self, contour_img: np.ndarray):
        contour_rgb = cv2.cvtColor(contour_img, cv2.COLOR_BGR2RGB)
        h, w, ch = contour_rgb.shape
        q_image = QImage(contour_rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._contours_pixmap = QPixmap.fromImage(q_image)
        self.lblContours.setPixmap(self._contours_pixmap)

    def set_stats(self, text: str):
        self.lblStats.setText(text)

    def _save_result(self):
        if self._contours_pixmap is None:
            return
        pictures_dir = os.path.expanduser("~/Pictures/mis_monedas")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = os.path.join(pictures_dir, f"comparison_{timestamp}.png")

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Result", default_path, "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        if path:
            self._contours_pixmap.save(path)

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
