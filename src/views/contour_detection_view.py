import os
import cv2
import numpy as np
from datetime import datetime
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget, QFileDialog
from PyQt6.QtGui import QPixmap, QImage

from ..utils.image_utils import ImageUtils


class ContourDetectionView(QWidget):
    view_closed = pyqtSignal()
    load_image_requested = pyqtSignal()
    detection_params_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._result_pixmap: QPixmap | None = None
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "contour_detection_widget.ui")
        uic.loadUi(ui_path, self)

        self.btnLoadImage.clicked.connect(self.load_image_requested.emit)
        self.btnSaveResult.clicked.connect(self._save_result)

        self.rdoThreshold.toggled.connect(self.detection_params_changed.emit)
        self.sliderThreshold.valueChanged.connect(self._on_threshold_changed)
        self.sliderCannyLow.valueChanged.connect(self._on_canny_low_changed)
        self.sliderCannyHigh.valueChanged.connect(self._on_canny_high_changed)
        self.sliderMinArea.valueChanged.connect(self._on_min_area_changed)

    def _on_threshold_changed(self, value: int):
        self.lblThresholdValue.setText(str(value))
        self.detection_params_changed.emit()

    def _on_canny_low_changed(self, value: int):
        self.lblCannyLowValue.setText(str(value))
        self.detection_params_changed.emit()

    def _on_canny_high_changed(self, value: int):
        self.lblCannyHighValue.setText(str(value))
        self.detection_params_changed.emit()

    def _on_min_area_changed(self, value: int):
        self.lblMinAreaValue.setText(str(value))
        self.detection_params_changed.emit()

    # ── image loading ────────────────────────────────────────

    def load_image(self) -> str:
        return ImageUtils.open_image_file_dialog()

    # ── detection parameters ─────────────────────────────────

    def get_use_canny(self) -> bool:
        return self.rdoCanny.isChecked()

    def get_threshold(self) -> int:
        return self.sliderThreshold.value()

    def get_canny_low(self) -> int:
        return self.sliderCannyLow.value()

    def get_canny_high(self) -> int:
        return self.sliderCannyHigh.value()

    def get_min_area(self) -> int:
        return self.sliderMinArea.value()

    # ── result display ───────────────────────────────────────

    def display_result(self, contour_img: np.ndarray):
        rgb = cv2.cvtColor(contour_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        q_image = QImage(rgb.data, w, h, w * ch, QImage.Format.Format_RGB888)
        self._result_pixmap = QPixmap.fromImage(q_image)
        self.lblImage.setPixmap(
            self._result_pixmap.scaled(
                self.lblImage.size(), Qt.AspectRatioMode.KeepAspectRatio
            )
        )

    def set_stats(self, text: str):
        self.lblStats.setText(text)

    def _save_result(self):
        if self._result_pixmap is None:
            return
        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_path = os.path.join(pictures_dir, f"contours_{timestamp}.png")

        path, _ = QFileDialog.getSaveFileName(
            self, "Save Result", default_path, "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        if path:
            self._result_pixmap.save(path)

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
