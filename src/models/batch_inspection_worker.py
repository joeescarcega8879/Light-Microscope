import logging

from PyQt6.QtCore import QThread, pyqtSignal

from ..inspection.batch import run_batch
from ..inspection.reference import ReferenceSet

log = logging.getLogger(__name__)


class BatchInspectionWorker(QThread):
    progress = pyqtSignal(int, int, object)   # done, total, BatchItem
    batch_finished = pyqtSignal(object)       # BatchSummary
    batch_failed = pyqtSignal(str)

    def __init__(self, folder: str, ref: ReferenceSet, output_dir: str, copy_ok: bool, parent=None):
        super().__init__(parent)
        self._folder, self._ref = folder, ref
        self._output_dir, self._copy_ok = output_dir, copy_ok
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            summary = run_batch(
                self._folder, self._ref, self._output_dir or None, self._copy_ok,
                progress=lambda i, n, item: self.progress.emit(i, n, item),
                cancel=lambda: self._cancel,
            )
            self.batch_finished.emit(summary)
        except Exception as exc:
            log.exception("Batch inspection failed")
            self.batch_failed.emit(str(exc))
