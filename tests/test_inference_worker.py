import threading
import time

import numpy as np
from PyQt6.QtCore import QCoreApplication

from src.models.inference_worker import InferenceWorker


class FakeInferencer:
    def __init__(self, fail=False):
        self.fail = fail
        self.thread_ids = []

    def predict_frame(self, frame):
        self.thread_ids.append(threading.get_ident())
        if self.fail:
            raise RuntimeError("boom")
        return [(0, "part", 0.9, 0.5, 0.5, 0.1, 0.1)]


def _wait_for(app, cond, timeout=3.0):
    end = time.time() + timeout
    while time.time() < end and not cond():
        app.processEvents()
        time.sleep(0.01)
    return cond()


def test_worker_runs_off_main_thread_and_emits_result():
    app = QCoreApplication.instance() or QCoreApplication([])
    fake = FakeInferencer()
    worker = InferenceWorker(fake)
    results = []
    worker.result_ready.connect(lambda frame, dets: results.append((frame, dets)))
    worker.start()
    frame = np.zeros((4, 4, 3), np.uint8)
    worker.submit(frame)

    assert _wait_for(app, lambda: len(results) == 1)
    worker.stop()
    assert results[0][0] is frame
    assert len(results[0][1]) == 1
    assert fake.thread_ids[0] != threading.get_ident()


def test_worker_survives_inference_errors():
    app = QCoreApplication.instance() or QCoreApplication([])
    worker = InferenceWorker(FakeInferencer(fail=True))
    results = []
    worker.result_ready.connect(lambda frame, dets: results.append(dets))
    worker.start()
    worker.submit(np.zeros((4, 4, 3), np.uint8))

    assert _wait_for(app, lambda: len(results) == 1)
    worker.stop()
    assert results == [[]]
