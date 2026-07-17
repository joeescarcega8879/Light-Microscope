import os
import cv2
import time
from pathlib import Path
from uuid import uuid4
from typing import Optional
from datetime import datetime
from PyQt6.QtCore import pyqtSlot, QObject, QTimer, Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QFileDialog

from ..models.device_camera_startup import DeviceCameraStartup
from ..models.yolo_inferencer import YoloInferencer
from ..utils.image_utils import TypeCapture

# Per-class color palette for detection boxes (BGR order doesn't matter here — these are QColors)
_DET_COLORS = [
    QColor(50,  205, 50),   # lime green
    QColor(220, 20,  60),   # crimson
    QColor(30,  144, 255),  # dodger blue
    QColor(255, 215, 0),    # gold
    QColor(255, 105, 180),  # hot pink
    QColor(0,   206, 209),  # dark turquoise
    QColor(255, 140, 0),    # dark orange
    QColor(147, 112, 219),  # medium purple
]

# Run inference every N raw frames (throttle — CPU inference ~100ms each)
_INFERENCE_EVERY_N_FRAMES = 5


class DeviceCameraPresenter(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self._capture_thread: Optional[DeviceCameraStartup] = None
        self._current_pixmap: Optional[QPixmap] = None
        self._recording = False
        self._video_writer = None
        self._frame_count = 0
        self._recording_start = 0.0
        self._fps_timer = QTimer()
        self._fps_timer.timeout.connect(self._update_fps)
        self._recording_timer = QTimer()
        self._recording_timer.timeout.connect(self._update_recording_timer)

        # detection
        self._inferencer: YoloInferencer = YoloInferencer()
        self._detection_enabled: bool = False
        self._last_detections: list = []
        self._raw_frame_counter: int = 0

        self._connect_signals()

    def _connect_signals(self):
        self.view.connect_requested.connect(self._on_connect_requested)
        self.view.snapshot_requested.connect(self._take_snapshot)
        self.view.recording_requested.connect(self._toggle_recording)
        self.view.view_closed.connect(self._stop_capture)
        self.view.load_model_requested.connect(self._load_detection_model)
        self.view.detection_toggled.connect(self._toggle_detection)

    def _on_connect_requested(self, camera_index: int):
        if camera_index >= 0:
            self._start_capture(camera_index)
        else:
            self._stop_capture()

    def _start_capture(self, camera_index: int):
        if self._capture_thread is not None:
            self._stop_capture()

        self._capture_thread = DeviceCameraStartup(camera_index, TypeCapture.General)
        self._capture_thread.change_pixmap_signal.connect(self._update_image)
        self._capture_thread.raw_frame_signal.connect(self._on_raw_frame)
        self._capture_thread.finished.connect(self._on_capture_finished)
        self._capture_thread.start()

        self.view.set_connected(True)
        self._frame_count = 0
        self._fps_timer.start(1000)

    def _stop_capture(self):
        if self._recording:
            self._stop_recording()

        if self._capture_thread is not None:
            self._capture_thread.stop()
            self._capture_thread = None

        self._current_pixmap = None
        self._fps_timer.stop()
        self.view.set_connected(False)
        self.view.lblFeed.clear()
        self.view.lblFeed.setText("No camera connected")
        self.view.lblFps.setText("FPS: --")
        self.view.lblResolution.setText("-- x --")

    def _on_capture_finished(self):
        self._stop_capture()

    @pyqtSlot(QPixmap)
    def _update_image(self, pixmap: QPixmap):
        self._current_pixmap = pixmap
        self._frame_count += 1

        if self._detection_enabled and self._last_detections:
            pixmap = self._draw_detections(pixmap, self._last_detections)

        self.view.update_feed(pixmap)

    @pyqtSlot(object)
    def _on_raw_frame(self, frame):
        # recording
        if self._recording and self._video_writer is not None:
            self._video_writer.write(frame)

        # live detection — run every N frames to avoid blocking the UI
        if self._detection_enabled and self._inferencer.is_loaded():
            self._raw_frame_counter += 1
            if self._raw_frame_counter >= _INFERENCE_EVERY_N_FRAMES:
                self._raw_frame_counter = 0
                try:
                    self._last_detections = self._inferencer.predict_frame(frame)
                    self.view.set_detect_count(len(self._last_detections))
                except Exception:
                    self._last_detections = []

    def _update_fps(self):
        self.view.lblFps.setText(f"FPS: {self._frame_count}")
        self._frame_count = 0

    def _take_snapshot(self):
        if self._current_pixmap is None:
            print("No image to save")
            return
        
        take_by_quantity = self.view.get_info_from_ui()
        if take_by_quantity is not None:
            quantity = take_by_quantity.get("value")
            model_name = take_by_quantity.get("model_name")
            print(f"Taking {quantity} snapshots based on user input.")
            
            for i in range(quantity):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                mkdir_path = os.path.expanduser(f"~/Pictures/{model_name}")
                os.makedirs(mkdir_path, exist_ok=True)
                filename = os.path.join(os.path.expanduser(f"~/Pictures/{model_name}"), f"microscope_{uuid4()}_{i+1}.png")
                self._current_pixmap.save(filename)
                print(f"Snapshot {i+1} saved to {filename}")
            return

        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(pictures_dir, f"microscope_{timestamp}.png")
        self._current_pixmap.save(filename)
        print(f"Snapshot saved to {filename}")
        
    def _take_by_custom_quantity(self):
        
        if self._current_pixmap is None:
            print("No image to save")
            return
        
        pictures_dir = os.path.expanduser("~/Pictures/mis_monedas")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    
    def _toggle_recording(self, start: bool):
        if start:
            self._start_recording()
        else:
            self._stop_recording()

    def _start_recording(self):
        if self._capture_thread is None:
            return

        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(pictures_dir, f"recording_{timestamp}.avi")

        fourcc = cv2.VideoWriter_fourcc(*"XVID")
        self._video_writer = cv2.VideoWriter(filename, fourcc, 30.0, (1280, 720))
        self._recording = True
        self._recording_start = time.time()

        self.view.btnRecord.setText("Stop")
        self.view.lblTimer.setVisible(True)
        self.view.lblTimer.setText("00:00")
        self._recording_timer.start(500)

    def _stop_recording(self):
        self._recording = False
        if self._video_writer is not None:
            self._video_writer.release()
            self._video_writer = None

        self._recording_timer.stop()
        self.view.btnRecord.setText("Record")
        self.view.lblTimer.setVisible(False)

    def _update_recording_timer(self):
        elapsed = int(time.time() - self._recording_start)
        minutes = elapsed // 60
        seconds = elapsed % 60
        self.view.lblTimer.setText(f"{minutes:02d}:{seconds:02d}")

    # ── detection ─────────────────────────────────────────────

    def _load_detection_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self.view,
            "Load trained model",
            str(Path.home() / "Downloads"),
            "PyTorch model (*.pt);;All files (*)",
        )
        if not path:
            return
        try:
            self._inferencer.load_model(path)
            import os
            self.view.set_detection_model_loaded(os.path.basename(path))
        except RuntimeError as exc:
            self.view.set_detection_model_failed(str(exc))

    def _toggle_detection(self, enabled: bool):
        self._detection_enabled = enabled
        self._last_detections = []
        self._raw_frame_counter = 0
        self.view.set_detection_active(enabled)
        if not enabled:
            self.view.set_detect_count(0)

    @staticmethod
    def _draw_detections(pixmap: QPixmap, detections: list) -> QPixmap:
        """Draws bounding boxes + labels on a copy of pixmap."""
        result  = pixmap.copy()
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pw = pixmap.width()
        ph = pixmap.height()

        font = QFont()
        font.setPointSize(9)
        font.setBold(True)
        painter.setFont(font)

        for cls_id, name, conf, cx, cy, bw, bh in detections:
            color = _DET_COLORS[cls_id % len(_DET_COLORS)]

            x1 = int((cx - bw / 2) * pw)
            y1 = int((cy - bh / 2) * ph)
            x2 = int((cx + bw / 2) * pw)
            y2 = int((cy + bh / 2) * ph)

            # bounding box
            painter.setPen(QPen(color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)

            # label background + text
            label     = f"{name}  {conf:.0%}"
            label_w   = len(label) * 8 + 6
            label_h   = 18
            label_y   = max(0, y1 - label_h)

            bg = QColor(color)
            bg.setAlpha(210)
            painter.fillRect(x1, label_y, label_w, label_h, bg)
            painter.setPen(QPen(Qt.GlobalColor.white))
            painter.drawText(x1 + 3, label_y + label_h - 4, label)

        painter.end()
        return result
