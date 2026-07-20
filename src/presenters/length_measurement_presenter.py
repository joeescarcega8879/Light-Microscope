import csv
import math

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QFileDialog


class LengthMeasurementPresenter(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self._scale_factor: float | None = None  # real-world units per pixel
        self._unit = "px"
        self._px_lengths: list[float] = []
        self._connect_signals()

    def _connect_signals(self):
        self.view.load_image_requested.connect(self.view.load_image)
        self.view.set_scale_requested.connect(self._on_set_scale)
        self.view.delete_measurement_requested.connect(self._on_delete_measurement)
        self.view.clear_all_requested.connect(self._on_clear_all)
        self.view.export_csv_requested.connect(self._on_export_csv)
        self.view.canvas.measurement_completed.connect(self._on_measurement_completed)

    def _on_set_scale(self):
        known_pixels = self.view.get_known_pixels()
        if known_pixels <= 0:
            return
        self._scale_factor = self.view.get_real_length() / known_pixels
        self._unit = self.view.get_unit()
        self.view.set_scale_info(f"Scale: 1 px = {self._scale_factor:.4f} {self._unit}")
        for row, px_length in enumerate(self._px_lengths):
            self.view.update_row_unit_length(row, self._unit_text(px_length))

    def _on_measurement_completed(self, x1, y1, x2, y2):
        px_length = math.hypot(x2 - x1, y2 - y1)
        self._px_lengths.append(px_length)
        self.view.add_measurement_row(px_length, self._unit_text(px_length))

    def _unit_text(self, px_length: float) -> str:
        if self._scale_factor is None:
            return "—"
        return f"{px_length * self._scale_factor:.4f} {self._unit}"

    def _on_delete_measurement(self):
        row = self.view.get_selected_row()
        if row < 0:
            return
        del self._px_lengths[row]
        self.view.remove_row(row)
        self.view.canvas.remove_measurement(row)

    def _on_clear_all(self):
        self._px_lengths.clear()
        self.view.clear_table()
        self.view.canvas.clear_measurements()

    def _on_export_csv(self):
        if not self._px_lengths:
            return
        file_path, _ = QFileDialog.getSaveFileName(
            self.view, "Export Measurements", "", "CSV Files (*.csv)"
        )
        if not file_path:
            return
        with open(file_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["#", "Length (px)", f"Length ({self._unit})"])
            for i, px_length in enumerate(self._px_lengths):
                real = f"{px_length * self._scale_factor:.4f}" if self._scale_factor else ""
                writer.writerow([i + 1, f"{px_length:.2f}", real])
