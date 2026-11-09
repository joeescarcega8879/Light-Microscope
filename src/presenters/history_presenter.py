import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..data.history import Filters, HistoryRepository
from ..data.session import Session
from ..utils.pdf_report import generate_batch_report
from ..utils.platform_utils import open_folder

log = logging.getLogger(__name__)
INSPECTION_LIMIT = 1000


class HistoryPresenter(QObject):
    def __init__(self, view, repo: HistoryRepository, session: Session):
        super().__init__()
        self.view, self.repo, self.session = view, repo, session
        v = view
        v.filters_changed.connect(self.refresh_all)
        v.inspection_filters_changed.connect(self._refresh_inspections)
        v.audit_search_changed.connect(self._refresh_audit)
        v.batch_pdf_requested.connect(self._export_pdf)
        v.batch_folder_requested.connect(self._open_batch_folder)
        v.batch_delete_requested.connect(self._delete_batch)
        v.batch_items_requested.connect(v.show_inspections_for_batch)
        v.export_csv_requested.connect(self._export_csv)

        v.set_can_export(session.can("export_reports"))
        v.set_can_delete(session.can("delete_history"))
        v.set_audit_visible(session.can("view_audit"))
        self.refresh_all()

    # ── filters ──
    def _period_dates(self) -> tuple[Optional[str], Optional[str]]:
        period, today = self.view.period(), date.today()
        if period == "Today":
            return today.isoformat(), today.isoformat()
        if period == "Last 7 days":
            return (today - timedelta(days=6)).isoformat(), today.isoformat()
        if period == "Last 30 days":
            return (today - timedelta(days=29)).isoformat(), today.isoformat()
        if period == "Custom":
            a, b = self.view.custom_dates()
            return (a, b) if a <= b else (b, a)
        return None, None

    def _base_filters(self) -> Filters:
        d_from, d_to = self._period_dates()
        return Filters(date_from=d_from, date_to=d_to, reference=self.view.reference())

    # ── refresh ──
    def refresh_all(self):
        self.view.set_references(self.repo.references_used())
        f = self._base_filters()
        self.view.set_stats(self.repo.stats(f))
        self.view.set_batches(self.repo.list_batches(f))
        self._refresh_inspections()
        self._refresh_audit()

    def _refresh_inspections(self):
        f = self._base_filters()
        f.verdict, f.text = self.view.verdict(), self.view.text() or None
        batch_id = self.view.batch_filter_id()
        if batch_id is not None:           # drilling into one batch ignores the period filter
            f = Filters(verdict=f.verdict, text=f.text, batch_id=batch_id)
        self.view.set_inspections(self.repo.query_inspections(f, limit=INSPECTION_LIMIT), INSPECTION_LIMIT)

    def _refresh_audit(self, text: str = ""):
        if self.session.can("view_audit"):
            self.view.set_audit(self.repo.audit_entries(text=text or None))

    # ── actions ──
    def _export_pdf(self, batch_id: int):
        if not self.session.can("export_reports"):
            return
        batch = self.repo.get_batch(batch_id)
        if batch is None:
            return
        path, _ = QFileDialog.getSaveFileName(self.view, "Save PDF report",
                                              str(Path.home() / f"inspection_batch_{batch_id}.pdf"), "PDF (*.pdf)")
        if not path:
            return
        try:
            generate_batch_report(path, batch, self.repo.batch_items(batch_id))
        except Exception as exc:
            log.exception("PDF report failed")
            QMessageBox.warning(self.view, "Report", f"Could not create the report:\n{exc}")
            return
        self.session.audit("export_pdf", f"batch #{batch_id} -> {path}")
        QMessageBox.information(self.view, "Report", f"Report saved to:\n{path}")

    def _export_csv(self):
        if not self.session.can("export_reports"):
            return
        path, _ = QFileDialog.getSaveFileName(self.view, "Export inspections",
                                              str(Path.home() / "inspections.csv"), "CSV (*.csv)")
        if not path:
            return
        f = self._base_filters()
        f.verdict, f.text = self.view.verdict(), self.view.text() or None
        if self.view.batch_filter_id() is not None:
            f = Filters(verdict=f.verdict, text=f.text, batch_id=self.view.batch_filter_id())
        try:
            n = self.repo.export_csv(path, self.repo.query_inspections(f, limit=1_000_000))
        except OSError as exc:
            QMessageBox.warning(self.view, "Export", f"Could not write the file:\n{exc}")
            return
        self.session.audit("export_csv", f"{n} rows -> {path}")
        QMessageBox.information(self.view, "Export", f"{n} row(s) exported to:\n{path}")

    def _open_batch_folder(self, batch_id: int):
        batch = self.repo.get_batch(batch_id)
        out = batch["output_dir"] if batch else None
        if out and Path(out).is_dir():
            open_folder(out)
        else:
            QMessageBox.information(self.view, "Results folder",
                                    "This batch has no results folder (or it was moved or deleted).")

    def _delete_batch(self, batch_id: int):
        if not self.session.can("delete_history"):
            return
        answer = QMessageBox.question(self.view, "Delete batch",
                                      f"Delete batch #{batch_id} and its history records?\n"
                                      "Result files on disk are not touched.")
        if answer == QMessageBox.StandardButton.Yes:
            self.repo.delete_batch(batch_id)
            self.session.audit("delete_batch", f"batch #{batch_id}")
            self.refresh_all()
