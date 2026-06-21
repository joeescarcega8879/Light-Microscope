import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap

from ..utils.image_utils import ImageUtils


class ImageComparisonView(QWidget):
    load_image_a_requested = pyqtSignal()
    load_image_b_requested = pyqtSignal()
    compare_images_requested = pyqtSignal()
    view_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "image_comparison_widget.ui")
        uic.loadUi(ui_path, self)

        self.btnLoadA.clicked.connect(self.load_image_a_requested.emit)
        self.btnLoadB.clicked.connect(self.load_image_b_requested.emit)
        self.btnCompare.clicked.connect(self.compare_images_requested.emit)
        self.sliderThreshold.valueChanged.connect(
            lambda v: self.lblThresholdValue.setText(str(v))
        )

    def get_threshold(self) -> int:
        return self.sliderThreshold.value()

    def get_image_a(self) -> QPixmap | None:
        return self.lblImageA.pixmap() or None

    def get_image_b(self) -> QPixmap | None:
        return self.lblImageB.pixmap() or None

    def load_image_a(self):
        file_path = ImageUtils.open_image_file_dialog()
        if file_path:
            self.lblImageA.setPixmap(QPixmap(file_path))

    def load_image_b(self):
        file_path = ImageUtils.open_image_file_dialog()
        if file_path:
            self.lblImageB.setPixmap(QPixmap(file_path))

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
