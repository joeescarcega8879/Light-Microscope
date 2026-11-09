import logging
import threading
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from .yolo_inferencer import YoloInferencer

log = logging.getLogger(__name__)


class InferenceWorker(QThread):
    """Runs YOLO inference off the GUI thread.

    submit() keeps only the latest frame (older pending frames are dropped), so
    a slow model never builds a backlog. The result is emitted together with the
    frame it was computed on, so consumers can compare detections to that frame.
    """
    result_ready = pyqtSignal(object, object)  # frame, detections

    def __init__(self, inferencer: YoloInferencer, parent=None):
        super().__init__(parent)
        self._inferencer = inferencer
        self._pending: Optional[object] = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._running = True

    def submit(self, frame):
        with self._lock:
            self._pending = frame
        self._wake.set()

    def busy(self) -> bool:
        with self._lock:
            return self._pending is not None

    def stop(self):
        self._running = False
        self._wake.set()
        self.wait()

    def run(self):
        while self._running:
            self._wake.wait()
            self._wake.clear()
            if not self._running:
                break
            with self._lock:
                frame, self._pending = self._pending, None
            if frame is None:
                continue
            try:
                detections = self._inferencer.predict_frame(frame)
            except Exception:
                log.exception("Live inference failed")
                detections = []
            self.result_ready.emit(frame, detections)
