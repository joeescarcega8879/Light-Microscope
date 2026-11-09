import os
import cv2
import time
import logging
import numpy as np
from pathlib import Path
from uuid import uuid4
from typing import Optional
from datetime import datetime
from PyQt6.QtCore import pyqtSlot, QObject, QTimer, Qt
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont
from PyQt6.QtWidgets import QFileDialog

from ..models.device_camera_startup import DeviceCameraStartup
from ..models.yolo_inferencer import YoloInferencer
from ..models.inference_worker import InferenceWorker
from ..utils.image_utils import TypeCapture, ImageUtils

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

log = logging.getLogger(__name__)

# Submit a frame for inference every N raw frames (inference itself runs in a worker thread)
_INFERENCE_EVERY_N_FRAMES = 5

# Reference / anomaly check
_MISMATCH_COLOR = QColor(255, 0, 0)     # pure red — distinct from crimson already in _DET_COLORS
_ANOMALY_COLOR = QColor(255, 255, 0)    # pure yellow — not present in _DET_COLORS
_MATCH_DISTANCE_CUTOFF = 0.15           # normalized centroid distance beyond which a live det is unmatched
_ANOMALY_PIXEL_PCT_CUTOFF = 8.0         # % changed pixels in a matched crop above which it's "anomaly"


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
        self._inference_worker: Optional[InferenceWorker] = None

        # reference / anomaly check
        self._last_raw_frame: Optional[np.ndarray] = None
        self._reference_frame: Optional[np.ndarray] = None
        self._reference_detections: list = []
        self._anomaly_check_enabled: bool = False
        self._last_status_by_index: dict = {}

        self._connect_signals()

    def _connect_signals(self):
        self.view.connect_requested.connect(self._on_connect_requested)
        self.view.snapshot_requested.connect(self._take_snapshot)
        self.view.recording_requested.connect(self._toggle_recording)
        self.view.view_closed.connect(self._stop_capture)
        self.view.load_model_requested.connect(self._load_detection_model)
        self.view.detection_toggled.connect(self._toggle_detection)
        self.view.reference_requested.connect(self._on_set_reference)
        self.view.anomaly_check_toggled.connect(self._toggle_anomaly_check)

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

        if self._detection_enabled:
            self._start_inference_worker()

        self.view.set_connected(True)
        self._frame_count = 0
        self._fps_timer.start(1000)

        if self._inferencer.is_loaded():
            self.view.set_detection_model_loaded(os.path.basename(self._inferencer.model_path()))

    def _stop_capture(self):
        self._stop_inference_worker()
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

        self._last_raw_frame = None
        self._reference_frame = None
        self._reference_detections = []
        self._anomaly_check_enabled = False
        self._last_status_by_index = {}

    def _on_capture_finished(self):
        self._stop_capture()

    @pyqtSlot(QPixmap)
    def _update_image(self, pixmap: QPixmap):
        self._current_pixmap = pixmap
        self._frame_count += 1

        if self._detection_enabled and self._last_detections:
            pixmap = self._draw_detections(pixmap, self._last_detections, self._last_status_by_index)

        self.view.update_feed(pixmap)

    @pyqtSlot(object)
    def _on_raw_frame(self, frame):
        self._last_raw_frame = frame

        # recording
        if self._recording and self._video_writer is not None:
            self._video_writer.write(frame)

        # live detection — submit every N frames to the worker thread (never blocks the UI)
        if self._detection_enabled and self._inference_worker is not None:
            self._raw_frame_counter += 1
            if self._raw_frame_counter >= _INFERENCE_EVERY_N_FRAMES and not self._inference_worker.busy():
                self._raw_frame_counter = 0
                self._inference_worker.submit(frame)

    @pyqtSlot(object, object)
    def _on_inference_result(self, frame, detections):
        if not self._detection_enabled:
            return
        self._last_detections = detections
        self.view.set_detect_count(len(detections))

        if self._anomaly_check_enabled and self._reference_frame is not None:
            self._last_status_by_index, counts = self._compare_to_reference(
                frame, detections,
                self._reference_frame, self._reference_detections,
                self.view.get_anomaly_sensitivity(),
            )
            ok, anomaly, mismatch, missing = counts
            self.view.set_anomaly_stats(
                f"{ok} ok · {anomaly} anomaly · {mismatch} mismatch · {missing} missing"
            )
        else:
            self._last_status_by_index = {}

    def _update_fps(self):
        self.view.lblFps.setText(f"FPS: {self._frame_count}")
        self._frame_count = 0

    def _take_snapshot(self):
        if self._current_pixmap is None:
            log.warning("No image to save")
            return
        
        take_by_quantity = self.view.get_info_from_ui()
        if take_by_quantity is not None:
            quantity = take_by_quantity.get("value")
            model_name = take_by_quantity.get("model_name")
            log.info("Taking %d snapshots based on user input.", quantity)
            
            for i in range(quantity):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                mkdir_path = os.path.expanduser(f"~/Pictures/{model_name}")
                os.makedirs(mkdir_path, exist_ok=True)
                filename = os.path.join(os.path.expanduser(f"~/Pictures/{model_name}"), f"microscope_{uuid4()}_{i+1}.png")
                self._current_pixmap.save(filename)
                log.info("Snapshot %d saved to %s", i + 1, filename)
            return

        pictures_dir = os.path.expanduser("~/Pictures")
        os.makedirs(pictures_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(pictures_dir, f"microscope_{timestamp}.png")
        self._current_pixmap.save(filename)
        log.info("Snapshot saved to %s", filename)
        
    def _take_by_custom_quantity(self):
        
        if self._current_pixmap is None:
            log.warning("No image to save")
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
            self.view.set_detection_model_loaded(os.path.basename(path))
            if self._detection_enabled:
                self._start_inference_worker()
        except RuntimeError as exc:
            self.view.set_detection_model_failed(str(exc))

    def _start_inference_worker(self):
        if self._inference_worker is None and self._inferencer.is_loaded():
            self._inference_worker = InferenceWorker(self._inferencer)
            self._inference_worker.result_ready.connect(self._on_inference_result)
            self._inference_worker.start()

    def _stop_inference_worker(self):
        if self._inference_worker is not None:
            self._inference_worker.stop()
            self._inference_worker = None

    def _toggle_detection(self, enabled: bool):
        self._detection_enabled = enabled
        if enabled:
            self._start_inference_worker()
        else:
            self._stop_inference_worker()
        self._last_detections = []
        self._raw_frame_counter = 0
        self.view.set_detection_active(enabled)
        if not enabled:
            self.view.set_detect_count(0)

    # ── reference / anomaly check ─────────────────────────────

    def _on_set_reference(self):
        if self._last_raw_frame is None or not self._inferencer.is_loaded():
            log.warning("No live frame / model available to set as reference")
            return
        try:
            detections = self._inferencer.predict_frame(self._last_raw_frame)
        except Exception:
            log.exception("Reference inference failed")
            detections = []

        self._reference_frame = self._last_raw_frame.copy()
        self._reference_detections = detections
        self.view.set_reference_status(
            f"Reference: {len(detections)} piece(s)" if detections else "Reference: 0 pieces (empty scene)"
        )
        self.view.set_anomaly_check_enabled(True)

    def _toggle_anomaly_check(self, enabled: bool):
        self._anomaly_check_enabled = enabled
        self._last_status_by_index = {}
        if not enabled:
            self.view.set_anomaly_stats("")

    @staticmethod
    def _compare_to_reference(frame, detections: list, reference_frame, reference_detections: list,
                              sensitivity: int) -> tuple[dict, tuple[int, int, int, int]]:
        """
        Matches live detections to reference detections by class + nearest centroid.

        Returns (status_by_index, (ok, anomaly, mismatch, missing)):
          - status_by_index maps index into `detections` -> "ok" | "anomaly" | "mismatch"
          - missing: reference detections with no matching live detection (nothing to draw)
        """
        ref_by_class: dict = {}
        for cls_id, _, _, cx, cy, w, h in reference_detections:
            ref_by_class.setdefault(cls_id, []).append((cx, cy, w, h))

        live_by_class: dict = {}
        for i, det in enumerate(detections):
            live_by_class.setdefault(det[0], []).append(i)

        status_by_index: dict = {}
        ok = anomaly = mismatch = missing = 0

        for cls_id in set(ref_by_class) | set(live_by_class):
            remaining_ref = list(ref_by_class.get(cls_id, []))

            for i in live_by_class.get(cls_id, []):
                _, _, _, cx, cy, w, h = detections[i]
                best_idx, best_dist = None, None
                for r_idx, (rcx, rcy, rw, rh) in enumerate(remaining_ref):
                    dist = ((cx - rcx) ** 2 + (cy - rcy) ** 2) ** 0.5
                    if best_dist is None or dist < best_dist:
                        best_idx, best_dist = r_idx, dist

                if best_idx is None or best_dist > _MATCH_DISTANCE_CUTOFF:
                    status_by_index[i] = "mismatch"
                    mismatch += 1
                    continue

                ref_box = remaining_ref.pop(best_idx)
                status = DeviceCameraPresenter._classify_crop(
                    reference_frame, ref_box, frame, (cx, cy, w, h), sensitivity
                )
                status_by_index[i] = status
                if status == "anomaly":
                    anomaly += 1
                else:
                    ok += 1

            missing += len(remaining_ref)

        return status_by_index, (ok, anomaly, mismatch, missing)

    @staticmethod
    def _classify_crop(ref_frame, ref_box, live_frame, live_box, sensitivity: int) -> str:
        ref_crop = DeviceCameraPresenter._crop(ref_frame, *ref_box)
        live_crop = DeviceCameraPresenter._crop(live_frame, *live_box)
        if ref_crop is None or live_crop is None:
            return "ok"

        if live_crop.shape[:2] != ref_crop.shape[:2]:
            live_crop = cv2.resize(live_crop, (ref_crop.shape[1], ref_crop.shape[0]))

        _, binary_mask, _ = ImageUtils.compute_diff(ref_crop, live_crop, threshold=sensitivity)
        changed_pct = 100.0 * np.count_nonzero(binary_mask) / binary_mask.size
        return "anomaly" if changed_pct > _ANOMALY_PIXEL_PCT_CUTOFF else "ok"

    @staticmethod
    def _crop(frame, cx, cy, w, h):
        fh, fw = frame.shape[:2]
        x1 = max(0, int((cx - w / 2) * fw))
        y1 = max(0, int((cy - h / 2) * fh))
        x2 = min(fw, int((cx + w / 2) * fw))
        y2 = min(fh, int((cy + h / 2) * fh))
        if x2 <= x1 or y2 <= y1:
            return None
        return frame[y1:y2, x1:x2]

    @staticmethod
    def _draw_detections(pixmap: QPixmap, detections: list, status_by_index: Optional[dict] = None) -> QPixmap:
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

        status_by_index = status_by_index or {}

        for i, (cls_id, name, conf, cx, cy, bw, bh) in enumerate(detections):
            status = status_by_index.get(i, "ok")
            if status == "mismatch":
                color = _MISMATCH_COLOR
            elif status == "anomaly":
                color = _ANOMALY_COLOR
            else:
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
            label = f"{name}  {conf:.0%}"
            if status in ("mismatch", "anomaly"):
                label += f"  [{status.upper()}]"
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
