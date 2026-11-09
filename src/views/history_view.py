from typing import Optional

from PyQt6.QtCore import QDate, Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDateEdit, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from .charts import ERROR_COLOR, NG_COLOR, OK_COLOR, HBarChart, StackedBarChart

_VERDICT_COLORS = {"OK": "#2e9e4f", "NG": "#d93636"}
PERIODS = ["All time", "Today", "Last 7 days", "Last 30 days", "Custom"]


def _table(headers: list[str]) -> QTableWidget:
    t = QTableWidget(0, len(headers))
    t.setHorizontalHeaderLabels(headers)
    t.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    t.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    t.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    t.setAlternatingRowColors(True)
    t.verticalHeader().setVisible(False)
    t.horizontalHeader().setStretchLastSection(True)
    t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    return t


def _fill(table: QTableWidget, rows: list[list], verdict_col: Optional[int] = None, ids: Optional[list] = None):
    table.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = QTableWidgetItem("" if value is None else str(value))
            if c == 0 and ids is not None:
                cell.setData(Qt.ItemDataRole.UserRole, ids[r])
            if c == verdict_col:
                cell.setForeground(QColor(_VERDICT_COLORS.get(str(value), "#d9a21b")))
            table.setItem(r, c, cell)


class HistoryView(QWidget):
    filters_changed = pyqtSignal()
    inspection_filters_changed = pyqtSignal()
    audit_search_changed = pyqtSignal(str)
    batch_pdf_requested = pyqtSignal(int)
    batch_folder_requested = pyqtSignal(int)
    batch_delete_requested = pyqtSignal(int)
    batch_items_requested = pyqtSignal(int)
    export_csv_requested = pyqtSignal()
    view_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("History & Statistics")
        self.resize(1100, 760)
        self._batch_filter_id: Optional[int] = None
        self._build()

    # ── construction ──
    def _build(self):
        root = QVBoxLayout(self)
        root.addLayout(self._build_filter_bar())
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        self.tabs.addTab(self._build_dashboard(), "Dashboard")
        self.tabs.addTab(self._build_batches(), "Batches")
        self.tabs.addTab(self._build_inspections(), "Inspections")
        self._audit_tab = self._build_audit()
        self.tabs.addTab(self._audit_tab, "Audit log")

    def _build_filter_bar(self) -> QHBoxLayout:
        bar = QHBoxLayout()
        bar.addWidget(QLabel("Period:"))
        self.cmbPeriod = QComboBox()
        self.cmbPeriod.addItems(PERIODS)
        bar.addWidget(self.cmbPeriod)
        self.dateFrom, self.dateTo = QDateEdit(QDate.currentDate()), QDateEdit(QDate.currentDate())
        for d in (self.dateFrom, self.dateTo):
            d.setCalendarPopup(True)
            d.setDisplayFormat("yyyy-MM-dd")
            d.setEnabled(False)
        bar.addWidget(QLabel("From"))
        bar.addWidget(self.dateFrom)
        bar.addWidget(QLabel("To"))
        bar.addWidget(self.dateTo)
        bar.addSpacing(16)
        bar.addWidget(QLabel("Reference:"))
        self.cmbReference = QComboBox()
        self.cmbReference.setMinimumWidth(160)
        bar.addWidget(self.cmbReference)
        bar.addStretch(1)
        self.btnRefresh = QPushButton("Refresh")
        bar.addWidget(self.btnRefresh)

        self.cmbPeriod.currentTextChanged.connect(self._on_period)
        for w in (self.dateFrom, self.dateTo):
            w.dateChanged.connect(lambda _=None: self.filters_changed.emit())
        self.cmbReference.activated.connect(lambda _=None: self.filters_changed.emit())
        self.btnRefresh.clicked.connect(self.filters_changed.emit)
        return bar

    def _kpi(self, title: str) -> tuple[QGroupBox, QLabel]:
        box = QGroupBox(title)
        lay = QVBoxLayout(box)
        value = QLabel("—")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        value.setStyleSheet("font-size: 26px; font-weight: bold;")
        lay.addWidget(value)
        return box, value

    def _build_dashboard(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self._kpis = {}
        for key, title in (("inspected", "Inspected"), ("ok", "OK"), ("ng", "NG"),
                           ("reject", "Reject rate"), ("errors", "Errors")):
            box, label = self._kpi(title)
            self._kpis[key] = label
            row.addWidget(box)
        self._kpis["ok"].setStyleSheet("font-size: 26px; font-weight: bold; color: #2e9e4f;")
        self._kpis["ng"].setStyleSheet("font-size: 26px; font-weight: bold; color: #d93636;")
        lay.addLayout(row)

        daily = QGroupBox("Parts per day")
        dl = QVBoxLayout(daily)
        self.chartDaily = StackedBarChart()
        dl.addWidget(self.chartDaily)
        lay.addWidget(daily, 3)

        byref = QGroupBox("Reject rate by reference (worst first)")
        bl = QVBoxLayout(byref)
        self.chartRefs = HBarChart()
        bl.addWidget(self.chartRefs)
        lay.addWidget(byref, 2)
        return w

    def _build_batches(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.tblBatches = _table(["ID", "Date", "Reference", "Inspector", "Parts", "OK", "NG", "Errors", "Folder"])
        lay.addWidget(self.tblBatches, 1)
        row = QHBoxLayout()
        self.btnShowItems = QPushButton("Show parts")
        self.btnPdf = QPushButton("PDF report…")
        self.btnOpenFolder = QPushButton("Open results folder")
        self.btnDeleteBatch = QPushButton("Delete batch")
        for b in (self.btnShowItems, self.btnPdf, self.btnOpenFolder):
            row.addWidget(b)
        row.addStretch(1)
        row.addWidget(self.btnDeleteBatch)
        lay.addLayout(row)
        self.btnShowItems.clicked.connect(lambda: self._emit_selected(self.batch_items_requested))
        self.btnPdf.clicked.connect(lambda: self._emit_selected(self.batch_pdf_requested))
        self.btnOpenFolder.clicked.connect(lambda: self._emit_selected(self.batch_folder_requested))
        self.btnDeleteBatch.clicked.connect(lambda: self._emit_selected(self.batch_delete_requested))
        return w

    def _build_inspections(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        row = QHBoxLayout()
        self.cmbVerdict = QComboBox()
        self.cmbVerdict.addItems(["All", "OK", "NG", "ERROR"])
        self.lineSearch = QLineEdit()
        self.lineSearch.setPlaceholderText("Search file name…")
        self.lblBatchFilter = QLabel("")
        self.btnClearBatch = QPushButton("Show all batches")
        self.btnClearBatch.hide()
        self.btnExportCsv = QPushButton("Export CSV…")
        for x in (QLabel("Verdict:"), self.cmbVerdict, self.lineSearch, self.lblBatchFilter, self.btnClearBatch):
            row.addWidget(x)
        row.addStretch(1)
        row.addWidget(self.btnExportCsv)
        lay.addLayout(row)
        self.tblInspections = _table(["ID", "Batch", "Date", "File", "Reference", "Verdict", "Defects", "Area %", "Details"])
        lay.addWidget(self.tblInspections, 1)
        self.lblCount = QLabel("")
        lay.addWidget(self.lblCount)

        self.cmbVerdict.activated.connect(lambda _=None: self.inspection_filters_changed.emit())
        self.lineSearch.textChanged.connect(lambda _=None: self.inspection_filters_changed.emit())
        self.btnClearBatch.clicked.connect(self.clear_batch_filter)
        self.btnExportCsv.clicked.connect(self.export_csv_requested.emit)
        return w

    def _build_audit(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.lineAudit = QLineEdit()
        self.lineAudit.setPlaceholderText("Search user, action or detail…")
        lay.addWidget(self.lineAudit)
        self.tblAudit = _table(["Date", "User", "Action", "Detail"])
        lay.addWidget(self.tblAudit, 1)
        self.lineAudit.textChanged.connect(self.audit_search_changed.emit)
        return w

    # ── filters ──
    def _on_period(self, period: str):
        custom = period == "Custom"
        self.dateFrom.setEnabled(custom)
        self.dateTo.setEnabled(custom)
        self.filters_changed.emit()

    def period(self) -> str:
        return self.cmbPeriod.currentText()

    def custom_dates(self) -> tuple[str, str]:
        return self.dateFrom.date().toString("yyyy-MM-dd"), self.dateTo.date().toString("yyyy-MM-dd")

    def reference(self) -> Optional[str]:
        return self.cmbReference.currentText() if self.cmbReference.currentIndex() > 0 else None

    def set_references(self, names: list[str]):
        current = self.cmbReference.currentText()
        self.cmbReference.blockSignals(True)
        self.cmbReference.clear()
        self.cmbReference.addItem("All references")
        self.cmbReference.addItems(names)
        if current in names:
            self.cmbReference.setCurrentText(current)
        self.cmbReference.blockSignals(False)

    def verdict(self) -> Optional[str]:
        v = self.cmbVerdict.currentText()
        return None if v == "All" else v

    def text(self) -> str:
        return self.lineSearch.text().strip()

    def batch_filter_id(self) -> Optional[int]:
        return self._batch_filter_id

    def show_inspections_for_batch(self, batch_id: int):
        self._batch_filter_id = batch_id
        self.lblBatchFilter.setText(f"Batch #{batch_id}")
        self.btnClearBatch.show()
        self.tabs.setCurrentWidget(self.tblInspections.parentWidget())
        self.inspection_filters_changed.emit()

    def clear_batch_filter(self):
        self._batch_filter_id = None
        self.lblBatchFilter.setText("")
        self.btnClearBatch.hide()
        self.inspection_filters_changed.emit()

    # ── data in ──
    def set_stats(self, stats):
        self._kpis["inspected"].setText(f"{stats.inspected:,}")
        self._kpis["ok"].setText(f"{stats.ok:,}")
        self._kpis["ng"].setText(f"{stats.ng:,}")
        self._kpis["reject"].setText(f"{stats.reject_rate:.1f}%" if stats.inspected else "—")
        self._kpis["errors"].setText(f"{stats.errors:,}")
        days = [d for d, *_ in stats.per_day]
        self.chartDaily.set_data(days, [
            ("OK", OK_COLOR, [r[1] for r in stats.per_day]),
            ("NG", NG_COLOR, [r[2] for r in stats.per_day]),
            ("Error", ERROR_COLOR, [r[3] for r in stats.per_day]),
        ])
        self.chartRefs.set_data(
            [(ref, (ng / total * 100.0) if total else 0.0,
              f"{(ng / total * 100.0) if total else 0.0:.1f}%  ({ng}/{total})") for ref, total, ng in stats.per_reference],
            maximum=100.0)

    def set_batches(self, rows):
        _fill(self.tblBatches, [[r["id"], r["started_at"], r["reference"], r["username"] or "—", r["total"],
                                 r["ok"], r["ng"], r["errors"], r["folder"]] for r in rows],
              ids=[r["id"] for r in rows])

    def set_inspections(self, rows, limit: int):
        _fill(self.tblInspections, [[r["id"], r["batch_id"], r["ts"], r["file"], r["reference"], r["verdict"],
                                     r["defects"], f"{r['defect_area_pct']:.2f}", r["reasons"] or r["error"]]
                                    for r in rows], verdict_col=5, ids=[r["id"] for r in rows])
        more = f" (showing the first {limit}; narrow the filters or export CSV)" if len(rows) >= limit else ""
        self.lblCount.setText(f"{len(rows)} part(s){more}")

    def set_audit(self, rows):
        _fill(self.tblAudit, [[r["ts"], r["username"], r["action"], r["detail"]] for r in rows])

    def set_audit_visible(self, visible: bool):
        self.tabs.setTabVisible(self.tabs.indexOf(self._audit_tab), visible)

    def set_can_export(self, can: bool):
        for b in (self.btnPdf, self.btnExportCsv):
            b.setEnabled(can)
            b.setToolTip("" if can else "Requires the supervisor or administrator role")

    def set_can_delete(self, can: bool):
        self.btnDeleteBatch.setEnabled(can)
        self.btnDeleteBatch.setToolTip("" if can else "Requires the administrator role")

    # ── helpers ──
    def selected_batch_id(self) -> Optional[int]:
        rows = self.tblBatches.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.tblBatches.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _emit_selected(self, signal):
        bid = self.selected_batch_id()
        if bid is not None:
            signal.emit(bid)

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
