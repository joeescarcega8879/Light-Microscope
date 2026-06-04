import glob
import os
import platform
import cv2
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap

from ..utils.image_utils import TypePlatform


class DeviceCameraView(QWidget):
    connect_requested = pyqtSignal(int)
    snapshot_requested = pyqtSignal()
    recording_requested = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self._updating_ui = False
        self.initialize_components()
        self.populate_cameras()

    def initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "camera_view_widget.ui")
        uic.loadUi(ui_path, self)

        self.btnConnect.toggled.connect(self._on_connect_toggled)
        self.btnSnapshot.clicked.connect(self.snapshot_requested.emit)
        self.btnRecord.toggled.connect(self.recording_requested.emit)

    def _on_connect_toggled(self, checked):
        if self._updating_ui:
            return
        if checked:
            data = self.cmbCamera.currentData()
            if data is not None:
                self.connect_requested.emit(data)
        else:
            self.connect_requested.emit(-1)

    def populate_cameras(self):
        self.cmbCamera.clear()
        found = False

        if platform.system() == TypePlatform.Linux.value:
            indices = set()
            for path in glob.glob("/dev/video*"):
                try:
                    idx = int(path.replace("/dev/video", ""))
                    indices.add(idx)
                except ValueError:
                    pass
            for idx in sorted(indices):
                cap = cv2.VideoCapture(idx, cv2.CAP_V4L2)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        name = self._get_v4l2_name(idx)
                        self.cmbCamera.addItem(name, idx)
                        found = True
                    cap.release()
        else:
            for i in range(10):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        self.cmbCamera.addItem(f"Camera {i}", i)
                        found = True
                    cap.release()

        if not found:
            self.cmbCamera.addItem("No camera found", None)
        self.btnConnect.setEnabled(found)

    @staticmethod
    def _get_v4l2_name(index: int) -> str:
        name_path = f"/sys/class/video4linux/video{index}/name"
        try:
            with open(name_path) as f:
                return f.read().strip()
        except OSError:
            return f"Camera {index}"

    def set_connected(self, connected: bool):
        self._updating_ui = True
        self.btnConnect.setChecked(connected)
        self._updating_ui = False
        self.btnConnect.setText("Disconnect" if connected else "Connect")
        self.cmbCamera.setEnabled(not connected)
        self.btnSnapshot.setEnabled(connected)
        self.btnRecord.setEnabled(connected)
        if not connected:
            self.btnRecord.setChecked(False)
            self.btnRecord.setText("Record")
            self.lblTimer.setVisible(False)

    def update_feed(self, pixmap: QPixmap):
        self.lblFeed.setPixmap(pixmap)
