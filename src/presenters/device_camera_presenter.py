import os
import cv2
import time
from typing import Optional
from datetime import datetime
from PyQt6.QtCore import pyqtSlot, QObject, QTimer
from PyQt6.QtGui import QPixmap

from ..models.device_camera_startup import DeviceCameraStartup
from ..utils.image_utils import TypeCapture


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
        self._connect_signals()

    def _connect_signals(self):
        self.view.connect_requested.connect(self._on_connect_requested)
        self.view.snapshot_requested.connect(self._take_snapshot)
        self.view.recording_requested.connect(self._toggle_recording)

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
        self.view.update_feed(pixmap)

    @pyqtSlot(object)
    def _on_raw_frame(self, frame):
        if self._recording and self._video_writer is not None:
            self._video_writer.write(frame)

    def _update_fps(self):
        self.view.lblFps.setText(f"FPS: {self._frame_count}")
        self._frame_count = 0

    def _take_snapshot(self):
        if self._current_pixmap is None:
            return

        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(pictures_dir, f"microscope_{timestamp}.png")
        self._current_pixmap.save(filename)

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
