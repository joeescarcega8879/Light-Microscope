import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMainWindow, QMessageBox


class MainView(QMainWindow):
    video_capture_requested = pyqtSignal()
    image_comparison_requested = pyqtSignal()
    measurement_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    ai_studio_requested = pyqtSignal()
    contour_detection_requested = pyqtSignal()
    part_inspection_requested = pyqtSignal()
    history_requested = pyqtSignal()
    sign_out_requested = pyqtSignal()

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
        self.btnInspect.clicked.connect(self.part_inspection_requested.emit)
        self.btnHistory.clicked.connect(self.history_requested.emit)

        self.actionSignOut = QAction("Sign out", self)
        self.menuFile.insertAction(self.actionExit, self.actionSignOut)
        self.actionSignOut.triggered.connect(self.sign_out_requested.emit)
        self.actionExit.triggered.connect(self.close)
        self.actionAbout.triggered.connect(self._show_about)

    def _show_about(self):
        QMessageBox.about(self, "About Light Microscope",
                          "Light Microscope\nInspect small parts: compare against a golden reference, "
                          "sort OK / NG, measure and train detection models.")

    def apply_permissions(self, session):
        """Enable only what the signed-in user's role allows, and show who is signed in."""
        self.btnInspect.setEnabled(session.can("run_inspection"))
        self.btnVideo.setEnabled(session.can("use_camera"))
        self.btnAiStudio.setEnabled(session.can("use_ai_studio"))
        self.btnHistory.setEnabled(session.can("view_history"))
        if not session.can("use_ai_studio"):
            self.btnAiStudio.setToolTip("AI Studio requires the supervisor or administrator role")
        self.statusBar().showMessage(f"Signed in as {session.username} ({session.role})")
