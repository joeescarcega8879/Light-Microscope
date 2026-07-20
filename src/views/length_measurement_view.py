import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QTableWidgetItem, QWidget

from .image_panel import MeasurementCanvas
from ..utils.image_utils import ImageUtils


class LengthMeasurementView(QWidget):
    view_closed = pyqtSignal()
    load_image_requested = pyqtSignal()
    set_scale_requested = pyqtSignal()
    delete_measurement_requested = pyqtSignal()
    clear_all_requested = pyqtSignal()
    export_csv_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "length_measurement_widget.ui")
        uic.loadUi(ui_path, self)
        self._promote_canvas()

        self.btnLoadImage.clicked.connect(self.load_image_requested.emit)
        self.btnZoomIn.clicked.connect(self.canvas.zoom_in)
        self.btnZoomOut.clicked.connect(self.canvas.zoom_out)
        self.btnZoomFit.clicked.connect(self.canvas.zoom_fit)
        self.btnSetScale.clicked.connect(self.set_scale_requested.emit)
        self.btnDeleteMeasurement.clicked.connect(self.delete_measurement_requested.emit)
        self.btnClearAll.clicked.connect(self.clear_all_requested.emit)
        self.btnExportCSV.clicked.connect(self.export_csv_requested.emit)

        self.canvas.mouse_moved.connect(
            lambda x, y: self.lblCoords.setText(f"x: {x:.1f}  y: {y:.1f}")
        )

    def _promote_canvas(self):
        """Swap the placeholder lblCanvas (QLabel) for a real MeasurementCanvas widget."""
        old_label = self.lblCanvas
        index = self.canvasLayout.indexOf(old_label)
        self.canvas = MeasurementCanvas(self)
        self.canvasLayout.insertWidget(index, self.canvas)
        old_label.setParent(None)
        old_label.deleteLater()

    # ── image loading ────────────────────────────────────────

    def load_image(self):
        file_path = ImageUtils.open_image_file_dialog()
        if file_path:
            self.canvas.set_image(file_path)

    # ── calibration ──────────────────────────────────────────

    def get_known_pixels(self) -> float:
        return self.spinKnownPixels.value()

    def get_real_length(self) -> float:
        return self.spinRealLength.value()

    def get_unit(self) -> str:
        return self.comboUnit.currentText()

    def set_scale_info(self, text: str):
        self.lblScaleInfo.setText(text)

    # ── measurements table ───────────────────────────────────

    def add_measurement_row(self, px_length: float, unit_text: str):
        row = self.tableMeasurements.rowCount()
        self.tableMeasurements.insertRow(row)
        self.tableMeasurements.setItem(row, 0, QTableWidgetItem(str(row + 1)))
        self.tableMeasurements.setItem(row, 1, QTableWidgetItem(f"{px_length:.2f}"))
        self.tableMeasurements.setItem(row, 2, QTableWidgetItem(unit_text))

    def update_row_unit_length(self, row: int, unit_text: str):
        self.tableMeasurements.setItem(row, 2, QTableWidgetItem(unit_text))

    def get_selected_row(self) -> int:
        rows = self.tableMeasurements.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def remove_row(self, row: int):
        self.tableMeasurements.removeRow(row)
        for r in range(row, self.tableMeasurements.rowCount()):
            self.tableMeasurements.setItem(r, 0, QTableWidgetItem(str(r + 1)))

    def clear_table(self):
        self.tableMeasurements.setRowCount(0)

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
