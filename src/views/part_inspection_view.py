from typing import Optional

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QHeaderView,
    QLabel, QLineEdit, QProgressBar, QPushButton, QRadioButton, QSpinBox, QSplitter,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from ..inspection.engine import InspectionParams, Roi
from ..utils.qt_image import bgr_to_qpixmap
from .roi_canvas import RoiCanvas


class PartInspectionView(QWidget):
    reference_selected = pyqtSignal(str)
    new_reference_requested = pyqtSignal()
    add_golden_requested = pyqtSignal()
    delete_reference_requested = pyqtSignal()
    save_settings_requested = pyqtSignal()
    export_reference_requested = pyqtSignal()
    import_reference_requested = pyqtSignal()
    browse_input_requested = pyqtSignal()
    browse_output_requested = pyqtSignal()
    run_requested = pyqtSignal()
    cancel_requested = pyqtSignal()
    open_results_requested = pyqtSignal()
    row_selected = pyqtSignal(int)      # index into the presenter's item list
    filter_changed = pyqtSignal(str)    # "All" | "OK" | "NG" | "ERROR"
    view_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Part Inspection")
        self.resize(1280, 800)
        self._build()

    # ── construction ──
    def _build(self):
        root = QHBoxLayout(self)
        split = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(split)
        split.addWidget(self._build_left())
        split.addWidget(self._build_right())
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 6)

    def _build_left(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        ref_box = QGroupBox("1. Golden reference")
        rl = QVBoxLayout(ref_box)
        row = QHBoxLayout()
        self.cmbReference = QComboBox()
        self.cmbReference.setMinimumWidth(180)
        self.btnNewRef = QPushButton("New…")
        self.btnAddGolden = QPushButton("Add image…")
        self.btnDeleteRef = QPushButton("Delete")
        for wdg in (self.cmbReference, self.btnNewRef, self.btnAddGolden, self.btnDeleteRef):
            row.addWidget(wdg)
        row.setStretch(0, 1)
        rl.addLayout(row)
        share = QHBoxLayout()
        self.btnExportRef = QPushButton("Export reference (.zip)…")
        self.btnImportRef = QPushButton("Import reference (.zip)…")
        share.addWidget(self.btnExportRef)
        share.addWidget(self.btnImportRef)
        share.addStretch(1)
        rl.addLayout(share)
        self.lblRefInfo = QLabel("No reference selected")
        rl.addWidget(self.lblRefInfo)

        self.canvas = RoiCanvas()
        rl.addWidget(self.canvas, 1)
        mode = QHBoxLayout()
        self.rdoInclude = QRadioButton("Inspect this area")
        self.rdoIgnore = QRadioButton("Ignore this area")
        self.rdoInclude.setChecked(True)
        self.btnClearRois = QPushButton("Clear areas")
        mode.addWidget(self.rdoInclude)
        mode.addWidget(self.rdoIgnore)
        mode.addStretch(1)
        mode.addWidget(self.btnClearRois)
        rl.addLayout(mode)
        hint = QLabel("Drag on the image to draw an area. Right-click an area to remove it. "
                      "With no 'inspect' area the whole image is inspected.")
        hint.setWordWrap(True)
        rl.addWidget(hint)
        lay.addWidget(ref_box, 1)

        par_box = QGroupBox("2. Pass / fail rules")
        form = QFormLayout(par_box)
        self.spnThreshold = self._spin(1, 255, 25, "Minimum gray-level difference counted as a change")
        self.spnBlur = self._spin(0, 31, 5, "Noise smoothing before comparing (0 = off)")
        self.spnMinArea = self._spin(1, 1_000_000, 30, "Ignore differences smaller than this many pixels")
        self.spnMaxDefects = self._spin(0, 1000, 0, "A part is NG when it has MORE defects than this")
        self.chkAlign = QCheckBox("Auto-align part to reference")
        self.chkAlign.setChecked(True)
        self.chkLight = QCheckBox("Compensate lighting differences")
        self.chkLight.setChecked(True)
        form.addRow("Sensitivity threshold", self.spnThreshold)
        form.addRow("Noise smoothing", self.spnBlur)
        form.addRow("Min defect size (px)", self.spnMinArea)
        form.addRow("Allowed defects", self.spnMaxDefects)
        form.addRow(self.chkAlign)
        form.addRow(self.chkLight)
        self.btnSaveSettings = QPushButton("Save areas && rules to reference")
        form.addRow(self.btnSaveSettings)
        lay.addWidget(par_box)

        self.cmbReference.activated.connect(lambda _: self.reference_selected.emit(self.cmbReference.currentText()))
        self.btnNewRef.clicked.connect(self.new_reference_requested.emit)
        self.btnAddGolden.clicked.connect(self.add_golden_requested.emit)
        self.btnDeleteRef.clicked.connect(self.delete_reference_requested.emit)
        self.btnSaveSettings.clicked.connect(self.save_settings_requested.emit)
        self.btnExportRef.clicked.connect(self.export_reference_requested.emit)
        self.btnImportRef.clicked.connect(self.import_reference_requested.emit)
        self.btnClearRois.clicked.connect(self.canvas.clear_rois)
        self.rdoInclude.toggled.connect(lambda on: self.canvas.set_mode("include" if on else "ignore"))
        return w

    def _build_right(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        run_box = QGroupBox("3. Inspect a batch")
        g = QVBoxLayout(run_box)
        self.lineInput = QLineEdit()
        self.lineInput.setPlaceholderText("Folder with part images")
        self.btnBrowseInput = QPushButton("Browse…")
        self.lineOutput = QLineEdit()
        self.lineOutput.setPlaceholderText("Results folder (NG parts + results.csv)")
        self.btnBrowseOutput = QPushButton("Browse…")
        for label, line, btn in (("Input", self.lineInput, self.btnBrowseInput),
                                 ("Output", self.lineOutput, self.btnBrowseOutput)):
            r = QHBoxLayout()
            r.addWidget(QLabel(label))
            r.addWidget(line, 1)
            r.addWidget(btn)
            g.addLayout(r)
        r = QHBoxLayout()
        self.chkCopyOk = QCheckBox("Also copy OK parts")
        self.btnRun = QPushButton("Run inspection")
        self.btnCancel = QPushButton("Cancel")
        self.btnCancel.setEnabled(False)
        self.btnOpenResults = QPushButton("Open results folder")
        self.btnOpenResults.setEnabled(False)
        r.addWidget(self.chkCopyOk)
        r.addStretch(1)
        for b in (self.btnRun, self.btnCancel, self.btnOpenResults):
            r.addWidget(b)
        g.addLayout(r)
        self.progress = QProgressBar()
        self.progress.setValue(0)
        g.addWidget(self.progress)
        lay.addWidget(run_box)

        res_box = QGroupBox("Results")
        rv = QVBoxLayout(res_box)
        top = QHBoxLayout()
        self.lblSummary = QLabel("No batch run yet")
        self.lblSummary.setStyleSheet("font-weight: bold;")
        self.cmbFilter = QComboBox()
        self.cmbFilter.addItems(["All", "OK", "NG", "ERROR"])
        top.addWidget(self.lblSummary, 1)
        top.addWidget(QLabel("Show:"))
        top.addWidget(self.cmbFilter)
        rv.addLayout(top)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["File", "Verdict", "Defects", "Defect area %", "Ref #"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        rv.addWidget(self.table, 2)

        self.lblPreview = QLabel("Select a result to preview it")
        self.lblPreview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lblPreview.setMinimumHeight(220)
        self.lblPreview.setStyleSheet("background: #1e1e1e; color: #aaa;")
        rv.addWidget(self.lblPreview, 3)
        self.lblReasons = QLabel("")
        self.lblReasons.setWordWrap(True)
        rv.addWidget(self.lblReasons)
        lay.addWidget(res_box, 1)

        self.btnBrowseInput.clicked.connect(self.browse_input_requested.emit)
        self.btnBrowseOutput.clicked.connect(self.browse_output_requested.emit)
        self.btnRun.clicked.connect(self.run_requested.emit)
        self.btnCancel.clicked.connect(self.cancel_requested.emit)
        self.btnOpenResults.clicked.connect(self.open_results_requested.emit)
        self.cmbFilter.currentTextChanged.connect(self.filter_changed.emit)
        self.table.itemSelectionChanged.connect(self._on_selection)
        return w

    @staticmethod
    def _spin(lo: int, hi: int, val: int, tip: str) -> QSpinBox:
        s = QSpinBox()
        s.setRange(lo, hi)
        s.setValue(val)
        s.setToolTip(tip)
        return s

    # ── reference / settings ──
    def set_reference_names(self, names: list[str], current: Optional[str] = None):
        self.cmbReference.blockSignals(True)
        self.cmbReference.clear()
        self.cmbReference.addItems(names)
        if current and current in names:
            self.cmbReference.setCurrentText(current)
        self.cmbReference.blockSignals(False)

    def set_reference_info(self, text: str):
        self.lblRefInfo.setText(text)

    def set_golden_image(self, img: Optional[np.ndarray]):
        self.canvas.set_image(img)

    def set_rois(self, rois: list[Roi]):
        self.canvas.set_rois(rois)

    def rois(self) -> list[Roi]:
        return self.canvas.rois()

    def get_params(self) -> InspectionParams:
        return InspectionParams(
            threshold=self.spnThreshold.value(), blur_ksize=self.spnBlur.value(),
            min_defect_area=self.spnMinArea.value(), max_defects=self.spnMaxDefects.value(),
            align=self.chkAlign.isChecked(), normalize_lighting=self.chkLight.isChecked(),
        )

    def set_params(self, p: InspectionParams):
        self.spnThreshold.setValue(p.threshold)
        self.spnBlur.setValue(p.blur_ksize)
        self.spnMinArea.setValue(p.min_defect_area)
        self.spnMaxDefects.setValue(p.max_defects)
        self.chkAlign.setChecked(p.align)
        self.chkLight.setChecked(p.normalize_lighting)

    def set_editing_enabled(self, enabled: bool):
        """Lock everything that changes a reference or its rules (role-based)."""
        for w in (self.btnNewRef, self.btnAddGolden, self.btnDeleteRef, self.btnSaveSettings,
                  self.btnImportRef, self.btnClearRois, self.rdoInclude, self.rdoIgnore,
                  self.canvas, self.spnThreshold, self.spnBlur, self.spnMinArea, self.spnMaxDefects,
                  self.chkAlign, self.chkLight):
            w.setEnabled(enabled)
        tip = "" if enabled else "Requires the supervisor or administrator role"
        for w in (self.btnNewRef, self.btnAddGolden, self.btnDeleteRef, self.btnSaveSettings, self.btnImportRef):
            w.setToolTip(tip)
        self.btnExportRef.setEnabled(enabled)

    # ── batch controls ──
    def input_dir(self) -> str:
        return self.lineInput.text().strip()

    def output_dir(self) -> str:
        return self.lineOutput.text().strip()

    def set_input_dir(self, path: str):
        self.lineInput.setText(path)

    def set_output_dir(self, path: str):
        self.lineOutput.setText(path)

    def copy_ok(self) -> bool:
        return self.chkCopyOk.isChecked()

    def set_running(self, running: bool):
        self.btnRun.setEnabled(not running)
        self.btnCancel.setEnabled(running)
        self.cmbReference.setEnabled(not running)

    def set_progress(self, done: int, total: int):
        self.progress.setMaximum(max(1, total))
        self.progress.setValue(done)

    def set_results_available(self, available: bool):
        self.btnOpenResults.setEnabled(available)

    # ── results ──
    def set_summary(self, text: str):
        self.lblSummary.setText(text)

    def populate_table(self, rows: list[tuple[int, object]]):
        """rows: (item_index, BatchItem)."""
        self.table.blockSignals(True)
        self.table.setRowCount(len(rows))
        for r, (idx, it) in enumerate(rows):
            cells = [it.path.name, it.verdict, str(it.defects), f"{it.defect_area_pct:.2f}", str(it.reference_index + 1)]
            for c, text in enumerate(cells):
                cell = QTableWidgetItem(text)
                if c == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, idx)
                if c == 1:
                    cell.setForeground(QColor({"OK": "#2e9e4f", "NG": "#d93636"}.get(it.verdict, "#d9a21b")))
                self.table.setItem(r, c, cell)
        self.table.blockSignals(False)

    def clear_preview(self):
        self.lblPreview.clear()
        self.lblPreview.setText("Select a result to preview it")
        self.lblReasons.setText("")

    def show_preview(self, img: Optional[np.ndarray], reasons: str = ""):
        if img is None:
            self.lblPreview.clear()
            self.lblPreview.setText("No preview")
        else:
            pm = bgr_to_qpixmap(img).scaled(self.lblPreview.size(), Qt.AspectRatioMode.KeepAspectRatio,
                                            Qt.TransformationMode.SmoothTransformation)
            self.lblPreview.setPixmap(pm)
        self.lblReasons.setText(reasons)

    def _on_selection(self):
        rows = self.table.selectionModel().selectedRows()
        if rows:
            item = self.table.item(rows[0].row(), 0)
            self.row_selected.emit(int(item.data(Qt.ItemDataRole.UserRole)))

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
