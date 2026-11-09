import logging
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from ..inspection.engine import inspect_against_references
from ..inspection.imageio import IMAGE_EXTS, read_image
from ..inspection.reference import ReferenceSet, ReferenceStore
from ..models.batch_inspection_worker import BatchInspectionWorker
from ..utils import app_settings
from ..utils.platform_utils import open_folder

log = logging.getLogger(__name__)
_IMG_FILTER = "Images (" + " ".join(f"*{e}" for e in sorted(IMAGE_EXTS)) + ")"


class PartInspectionPresenter(QObject):
    def __init__(self, view, store: Optional[ReferenceStore] = None):
        super().__init__()
        self.view = view
        self._store = store or ReferenceStore()
        self._ref: Optional[ReferenceSet] = None
        self._ref_images: list = []
        self._items: list = []
        self._worker: Optional[BatchInspectionWorker] = None
        self._connect_signals()
        self._refresh_names(app_settings.settings().value("inspection/last_reference", "", str))

    def _connect_signals(self):
        v = self.view
        v.reference_selected.connect(self._select_reference)
        v.new_reference_requested.connect(self._new_reference)
        v.add_golden_requested.connect(self._add_golden)
        v.delete_reference_requested.connect(self._delete_reference)
        v.save_settings_requested.connect(self._save_settings)
        v.browse_input_requested.connect(self._browse_input)
        v.browse_output_requested.connect(self._browse_output)
        v.run_requested.connect(self._run)
        v.cancel_requested.connect(self._cancel)
        v.open_results_requested.connect(self._open_results)
        v.row_selected.connect(self._preview_item)
        v.filter_changed.connect(self._apply_filter)
        v.view_closed.connect(self._cancel_and_wait)

    # ── references ──
    def _refresh_names(self, current: str = ""):
        names = self._store.list_names()
        self.view.set_reference_names(names, current)
        target = current if current in names else (names[0] if names else "")
        if target:
            self._select_reference(target)
        else:
            self._ref = None
            self.view.set_golden_image(None)
            self.view.set_reference_info("No reference yet. Click 'New…' and pick images of a good part.")

    def _select_reference(self, name: str):
        if not name:
            return
        try:
            self._ref = self._store.load(name)
        except Exception as exc:
            log.exception("Could not load reference %s", name)
            self._warn(f"Could not load reference '{name}':\n{exc}")
            return
        self._ref_images = self._ref.load_images()
        self.view.set_reference_names(self._store.list_names(), name)
        self.view.set_golden_image(self._ref_images[0] if self._ref_images else None)
        self.view.set_rois(self._ref.rois)
        self.view.set_params(self._ref.params)
        self._update_info()
        app_settings.settings().setValue("inspection/last_reference", name)

    def _update_info(self):
        n = len(self._ref_images)
        self.view.set_reference_info(
            f"'{self._ref.name}': {n} golden image(s). A part passes if it matches any of them.")

    def _new_reference(self):
        name, ok = QInputDialog.getText(self.view, "New reference", "Product / reference name:")
        if not ok or not name.strip():
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self.view, "Select image(s) of a GOOD part", app_settings.get_last_dir("golden"), _IMG_FILTER)
        if not paths:
            return
        app_settings.set_last_dir(str(Path(paths[0]).parent), "golden")
        images = [i for i in (read_image(p) for p in paths) if i is not None]
        if not images:
            self._warn("None of the selected files could be read as images.")
            return
        try:
            ref = self._store.create(name, images, self.view.get_params())
        except (FileExistsError, ValueError, OSError) as exc:
            self._warn(str(exc))
            return
        self._refresh_names(ref.name)

    def _add_golden(self):
        if self._ref is None:
            self._warn("Create or select a reference first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self.view, "Add image(s) of a GOOD part", app_settings.get_last_dir("golden"), _IMG_FILTER)
        added = 0
        for p in paths:
            img = read_image(p)
            if img is not None:
                self._store.add_image(self._ref, img)
                added += 1
        if added:
            self._select_reference(self._ref.name)

    def _delete_reference(self):
        if self._ref is None:
            return
        answer = QMessageBox.question(self.view, "Delete reference",
                                      f"Delete reference '{self._ref.name}' and its images?")
        if answer == QMessageBox.StandardButton.Yes:
            self._store.delete(self._ref.name)
            self._ref = None
            self._refresh_names()

    def _apply_ui_to_ref(self):
        self._ref.params = self.view.get_params()
        self._ref.rois = self.view.rois()

    def _save_settings(self):
        if self._ref is None:
            return
        self._apply_ui_to_ref()
        self._store.save_settings(self._ref)
        self.view.set_reference_info(f"Saved areas and rules to '{self._ref.name}'.")

    # ── batch ──
    def _browse_input(self):
        d = QFileDialog.getExistingDirectory(self.view, "Folder with part images", app_settings.get_last_dir("batch_in"))
        if d:
            app_settings.set_last_dir(d, "batch_in")
            self.view.set_input_dir(d)
            if not self.view.output_dir():
                self.view.set_output_dir(str(Path(d) / "inspection_results"))

    def _browse_output(self):
        d = QFileDialog.getExistingDirectory(self.view, "Results folder", app_settings.get_last_dir("batch_out"))
        if d:
            app_settings.set_last_dir(d, "batch_out")
            self.view.set_output_dir(d)

    def _run(self):
        if self._ref is None or not self._ref_images:
            self._warn("Create or select a reference first.")
            return
        folder = self.view.input_dir()
        if not folder or not Path(folder).is_dir():
            self._warn("Choose a valid input folder.")
            return
        self._apply_ui_to_ref()
        self._store.save_settings(self._ref)   # keep the exact rules used for this run
        self._items = []
        self.view.populate_table([])
        self.view.set_summary("Running…")
        self.view.set_running(True)
        self.view.set_results_available(False)
        self._worker = BatchInspectionWorker(folder, self._ref, self.view.output_dir(), self.view.copy_ok())
        self._worker.progress.connect(self._on_progress)
        self._worker.batch_finished.connect(self._on_finished)
        self._worker.batch_failed.connect(self._on_failed)
        self._worker.start()

    def _on_progress(self, done: int, total: int, item):
        self._items.append(item)
        self.view.set_progress(done, total)
        self.view.set_summary(f"Inspecting… {done}/{total}")

    def _on_finished(self, summary):
        self._items = list(summary.items)
        self.view.set_running(False)
        state = "Cancelled — " if summary.cancelled else ""
        self.view.set_summary(f"{state}{len(summary.items)} parts:  {summary.ok} OK  ·  {summary.ng} NG  ·  {summary.errors} errors")
        self.view.set_results_available(bool(summary.output_dir))
        self._apply_filter(self.view.cmbFilter.currentText())
        self._worker = None

    def _on_failed(self, message: str):
        self.view.set_running(False)
        self.view.set_summary("Batch failed")
        self._warn(message)
        self._worker = None

    def _cancel(self):
        if self._worker is not None:
            self._worker.cancel()

    def _cancel_and_wait(self):
        if self._worker is not None:
            self._worker.cancel()
            self._worker.wait()
            self._worker = None

    def _open_results(self):
        out = self.view.output_dir()
        if out and Path(out).is_dir():
            open_folder(out)

    # ── results ──
    def _apply_filter(self, verdict: str):
        rows = [(i, it) for i, it in enumerate(self._items) if verdict == "All" or it.verdict == verdict]
        self.view.populate_table(rows)
        self.view.clear_preview()

    def _preview_item(self, index: int):
        if not (0 <= index < len(self._items)) or not self._ref_images:
            return
        item = self._items[index]
        img = read_image(item.path)
        if img is None:
            self.view.show_preview(None, item.error or "Could not read image")
            return
        try:
            res = inspect_against_references(self._ref_images, img, self._ref.params, self._ref.rois)
        except Exception as exc:
            log.exception("Preview failed")
            self.view.show_preview(None, str(exc))
            return
        reasons = "; ".join(res.reasons + res.warnings) or "No defects found."
        self.view.show_preview(res.overlay, f"{item.path.name}: {res.verdict} — {reasons}")

    def _warn(self, text: str):
        QMessageBox.warning(self.view, "Part Inspection", text)
