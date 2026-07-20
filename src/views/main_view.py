import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QMainWindow


class MainView(QMainWindow):
    video_capture_requested = pyqtSignal()
    image_comparison_requested = pyqtSignal()
    measurement_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    ai_studio_requested = pyqtSignal()
    contour_detection_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.ui")
        uic.loadUi(ui_path, self)

        self.btnVideo.clicked.connect(self.video_capture_requested.emit)
        self.btnImages.clicked.connect(self.image_comparison_requested.emit)
        self.btnMeasure.clicked.connect(self.measurement_requested.emit)
        self.btnSettings.clicked.connect(self.settings_requested.emit)
        self.btnAiStudio.clicked.connect(self.ai_studio_requested.emit)
        self.btnContours.clicked.connect(self.contour_detection_requested.emit)
