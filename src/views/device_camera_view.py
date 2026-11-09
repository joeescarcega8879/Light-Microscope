import os
import cv2
import glob
import logging
import platform
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtWidgets import QWidget
from PyQt6.QtGui import QPixmap

from ..utils.image_utils import TypePlatform

log = logging.getLogger(__name__)


class DeviceCameraView(QWidget):
    connect_requested     = pyqtSignal(int)
    snapshot_requested    = pyqtSignal()
    recording_requested   = pyqtSignal(bool)
    load_model_requested  = pyqtSignal()
    detection_toggled     = pyqtSignal(bool)
    reference_requested   = pyqtSignal()
    anomaly_check_toggled = pyqtSignal(bool)
    view_closed           = pyqtSignal()

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
        self.btnLoadModelCamera.clicked.connect(self.load_model_requested.emit)
        self.btnToggleDetection.toggled.connect(self.detection_toggled.emit)
        self.btnSetReference.clicked.connect(self.reference_requested.emit)
        self.btnToggleAnomalyCheck.toggled.connect(self.anomaly_check_toggled.emit)
        self.sliderAnomalySensitivity.valueChanged.connect(
            lambda v: self.lblAnomalySensitivityValue.setText(str(v))
        )

    def get_info_from_ui(self)-> dict:
        if self.rdb_by_quantity.isChecked():
            quantity_text = self.line_quantity.text()
            model_name = self.line_model_name.text()
            try:
                quantity = int(quantity_text)
                return {"mode": "quantity", "value": quantity, "model_name": model_name}
            except ValueError:
                log.warning("Invalid quantity input. Please enter a valid integer.")
                return None

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

    def set_detection_model_loaded(self, model_name: str):
        self.lblDetectionModel.setText(model_name)
        self.lblDetectionModel.setStyleSheet("color: green; font-size: 11px;")
        self.btnToggleDetection.setEnabled(True)
        self.btnSetReference.setEnabled(True)

    def set_detection_model_failed(self, message: str):
        self.lblDetectionModel.setText(f"Error: {message}")
        self.lblDetectionModel.setStyleSheet("color: red; font-size: 11px;")
        self.btnToggleDetection.setEnabled(False)
        self.btnSetReference.setEnabled(False)

    def set_detection_active(self, active: bool):
        self.btnToggleDetection.setText(
            "Disable Detection" if active else "Enable Detection"
        )

    def set_detect_count(self, count: int):
        self.lblDetectCount.setText(
            f"{count} detection(s)" if count > 0 else ""
        )

    # ── reference / anomaly check ────────────────────────────

    def get_anomaly_sensitivity(self) -> int:
        return self.sliderAnomalySensitivity.value()

    def set_reference_status(self, text: str):
        self.lblReferenceStatus.setText(text)

    def set_anomaly_stats(self, text: str):
        self.lblAnomalyStats.setText(text)

    def set_anomaly_check_enabled(self, enabled: bool):
        self.btnToggleAnomalyCheck.setEnabled(enabled)

    def set_connected(self, connected: bool):
        self._updating_ui = True
        self.btnConnect.setChecked(connected)
        self._updating_ui = False
        self.btnConnect.setText("Disconnect" if connected else "Connect")
        self.cmbCamera.setEnabled(not connected)
        self.btnSnapshot.setEnabled(connected)
        self.btnRecord.setEnabled(connected)
        self.rdb_by_quantity.setEnabled(connected)
        self.line_quantity.setEnabled(connected)
        self.line_model_name.setEnabled(connected)
        
        if not connected:
            self.btnRecord.setChecked(False)
            self.btnRecord.setText("Record")
            self.lblTimer.setVisible(False)
            self.btnToggleAnomalyCheck.setChecked(False)
            self.btnToggleAnomalyCheck.setEnabled(False)
            self.btnSetReference.setEnabled(False)
            self.lblReferenceStatus.setText("No reference set")
            self.lblAnomalyStats.setText("")

    def update_feed(self, pixmap: QPixmap):
        scaled = pixmap.scaled(
            self.lblFeed.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.lblFeed.setPixmap(scaled)

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
