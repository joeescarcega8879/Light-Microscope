import os
import cv2
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPixmap, QPolygon
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout

from ..utils.image_utils import ImageUtils

# ──────────────────────────────────────────────────────────────
# Per-class color palette
# ──────────────────────────────────────────────────────────────
_COLORS = [
    QColor(50, 205, 50),
    QColor(220, 20, 60),
    QColor(30, 144, 255),
    QColor(255, 215, 0),
    QColor(255, 105, 180),
    QColor(0, 206, 209),
    QColor(255, 140, 0),
    QColor(147, 112, 219),
]


def _class_color(class_id: int) -> QColor:
    return _COLORS[class_id % len(_COLORS)]


# ──────────────────────────────────────────────────────────────
# Custom drawing canvas
# ──────────────────────────────────────────────────────────────
class LabelingCanvas(QWidget):
    annotation_added = pyqtSignal()
    annotation_removed = pyqtSignal(int)
    pending_contour_changed = pyqtSignal(bool)   # True once a contour is selected, ready to confirm

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._cv_image = None   # np.ndarray BGR, same image as _pixmap, for contour detection
        self._annotations: list[tuple] = []   # (class_id, points: list[(x, y)] normalized)
        self._class_names: list[str] = []
        self._active_class: int = 0

        # All contours detected on the *whole* current image, live — like the
        # standalone Contour Detection module — plus which one is selected.
        self._contours_px: list = []          # cv2 contours (pixel coords), for hit-testing
        self._contours_norm: list = []        # same contours as normalized (x, y) point lists
        self._selected_index: int | None = None

        # Contour detection parameters, pushed in from the view's sliders.
        self._use_canny = False
        self._threshold = 127
        self._canny_low = 50
        self._canny_high = 150
        self._min_area = 0

        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    # ── public API ────────────────────────────────────────────

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self._cv_image = ImageUtils.qpixmap_to_numpy(pixmap)
        self._recompute_contours()

    def clear_image(self):
        self._pixmap = None
        self._cv_image = None
        self._annotations = []
        self._recompute_contours()

    def set_annotations(self, annotations: list[tuple]):
        self._annotations = list(annotations)
        self.update()

    def get_annotations(self) -> list[tuple]:
        return list(self._annotations)

    def set_class_names(self, names: list[str]):
        self._class_names = names

    def set_active_class(self, class_id: int):
        self._active_class = class_id

    def remove_annotation(self, index: int):
        if 0 <= index < len(self._annotations):
            self._annotations.pop(index)
            self.annotation_removed.emit(index)
            self.update()

    def set_contour_params(self, *, use_canny, threshold, canny_low, canny_high, min_area):
        self._use_canny = use_canny
        self._threshold = threshold
        self._canny_low = canny_low
        self._canny_high = canny_high
        self._min_area = min_area
        self._recompute_contours()

    def confirm_pending_annotation(self):
        if self._selected_index is None:
            return
        points = self._contours_norm[self._selected_index]
        self._annotations.append((self._active_class, points))
        self._set_selected(None)
        self.annotation_added.emit()

    def discard_pending_annotation(self):
        self._set_selected(None)

    # ── coordinate helpers ────────────────────────────────────

    def _image_rect(self) -> tuple[int, int, int, int]:
        """Returns (x_offset, y_offset, scaled_w, scaled_h)."""
        if not self._pixmap:
            return 0, 0, self.width(), self.height()
        scaled = self._pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - scaled.width()) // 2
        y = (self.height() - scaled.height()) // 2
        return x, y, scaled.width(), scaled.height()

    def _point_to_screen(self, x: float, y: float) -> QPoint:
        x0, y0, iw, ih = self._image_rect()
        return QPoint(int(x * iw) + x0, int(y * ih) + y0)

    # ── contour detection (whole image, live) ─────────────────

    def _set_selected(self, index: int | None):
        self._selected_index = index
        self.pending_contour_changed.emit(index is not None)
        self.update()

    def _recompute_contours(self):
        """Re-runs contour detection on the whole image with the current params
        — exactly like the standalone Contour Detection module's live preview."""
        self._contours_px = []
        self._contours_norm = []
        self._selected_index = None

        if self._cv_image is not None:
            img_h, img_w = self._cv_image.shape[:2]
            _, contours, _ = ImageUtils.detect_contours(
                self._cv_image,
                threshold=self._threshold,
                use_canny=self._use_canny,
                canny_low=self._canny_low,
                canny_high=self._canny_high,
                min_area=self._min_area,
            )
            for c in contours:
                epsilon = 0.002 * cv2.arcLength(c, True)
                approx = cv2.approxPolyDP(c, epsilon, True)
                if len(approx) >= 3:
                    self._contours_px.append(approx)
                    self._contours_norm.append([
                        (px / img_w, py / img_h) for px, py in approx.reshape(-1, 2)
                    ])

        self.pending_contour_changed.emit(False)
        self.update()

    def _contour_at(self, pos: QPoint) -> int | None:
        """Returns the index of the smallest detected contour containing `pos`, or None."""
        if self._cv_image is None or not self._contours_px:
            return None
        x0, y0, iw, ih = self._image_rect()
        if iw <= 0 or ih <= 0:
            return None
        nx = (pos.x() - x0) / iw
        ny = (pos.y() - y0) / ih
        if not (0.0 <= nx <= 1.0 and 0.0 <= ny <= 1.0):
            return None

        img_h, img_w = self._cv_image.shape[:2]
        point = (nx * img_w, ny * img_h)

        best_index, best_area = None, None
        for i, contour in enumerate(self._contours_px):
            if cv2.pointPolygonTest(contour, point, False) >= 0:
                area = cv2.contourArea(contour)
                if best_area is None or area < best_area:
                    best_index, best_area = i, area
        return best_index

    # ── paint ─────────────────────────────────────────────────

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # background
        painter.fillRect(self.rect(), QColor(40, 40, 40))

        if self._pixmap:
            x0, y0, iw, ih = self._image_rect()
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            painter.drawPixmap(x0, y0, scaled)

            font = QFont()
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)

            for class_id, points in self._annotations:
                color = _class_color(class_id)
                polygon = QPolygon([self._point_to_screen(x, y) for x, y in points])
                painter.setPen(QPen(color, 2))
                painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                painter.drawPolygon(polygon)

                label = (
                    self._class_names[class_id]
                    if class_id < len(self._class_names)
                    else str(class_id)
                )
                bbox = polygon.boundingRect()
                bg = QColor(color)
                bg.setAlpha(200)
                text_rect = QRect(bbox.left(), bbox.top() - 17, len(label) * 8 + 8, 17)
                painter.fillRect(text_rect, bg)
                painter.setPen(QPen(Qt.GlobalColor.white))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

            # live preview: every contour the current threshold/canny params detect
            painter.setPen(QPen(QColor(0, 200, 255), 1))
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            for i, points in enumerate(self._contours_norm):
                if i == self._selected_index:
                    continue
                painter.drawPolygon(QPolygon([self._point_to_screen(x, y) for x, y in points]))

            # the one the user clicked on, highlighted, awaiting confirmation
            if self._selected_index is not None:
                points = self._contours_norm[self._selected_index]
                painter.setPen(QPen(Qt.GlobalColor.yellow, 3))
                painter.drawPolygon(QPolygon([self._point_to_screen(x, y) for x, y in points]))

    # ── mouse ──────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._set_selected(self._contour_at(event.pos()))


# ──────────────────────────────────────────────────────────────
# Main view
# ──────────────────────────────────────────────────────────────
class YoloStudioView(QWidget):
    view_closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.canvas = LabelingCanvas()
        self._initialize_components()

    def _initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "yolo_studio_widget.ui")
        uic.loadUi(ui_path, self)

        # Inject LabelingCanvas into the canvasFrame placeholder
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.canvas)
        self.canvasFrame.setLayout(layout)

        # Training — model options (segmentation variants: annotations are contours/polygons)
        self.cmbModel.addItem("YOLOv8 Nano-Seg  (fastest, CPU-friendly)", "yolov8n-seg")
        self.cmbModel.addItem("YOLOv8 Small-Seg (more accurate, slower)", "yolov8s-seg")

        # Slider live labels
        self.sliderEpochs.valueChanged.connect(
            lambda v: self.lblEpochs.setText(str(v))
        )
        self.sliderValSplit.valueChanged.connect(
            lambda v: self.lblValSplit.setText(f"{v} %")
        )

        # Backend selector — update hint label and button visibility on change
        self.rdoLocal.toggled.connect(self._on_backend_changed)
        self.rdoModal.toggled.connect(self._on_backend_changed)
        self.rdoColab.toggled.connect(self._on_backend_changed)
        self._on_backend_changed()  # set initial state

        # Contour detection controls (Annotate tab) — drive the canvas's live preview
        self.rdoAnnThreshold.toggled.connect(self._on_contour_params_changed)
        self.rdoAnnCanny.toggled.connect(self._on_contour_params_changed)
        self.sliderAnnThreshold.valueChanged.connect(self._on_ann_threshold_changed)
        self.sliderAnnCannyLow.valueChanged.connect(self._on_ann_canny_low_changed)
        self.sliderAnnCannyHigh.valueChanged.connect(self._on_ann_canny_high_changed)
        self.sliderAnnMinArea.valueChanged.connect(self._on_ann_min_area_changed)
        self.canvas.pending_contour_changed.connect(self._on_pending_contour_changed)
        self._on_contour_params_changed()  # push initial slider values to the canvas

    # ── contour detection helpers ─────────────────────────────

    def _on_ann_threshold_changed(self, value: int):
        self.lblAnnThresholdValue.setText(str(value))
        self._on_contour_params_changed()

    def _on_ann_canny_low_changed(self, value: int):
        self.lblAnnCannyLowValue.setText(str(value))
        self._on_contour_params_changed()

    def _on_ann_canny_high_changed(self, value: int):
        self.lblAnnCannyHighValue.setText(str(value))
        self._on_contour_params_changed()

    def _on_ann_min_area_changed(self, value: int):
        self.lblAnnMinAreaValue.setText(str(value))
        self._on_contour_params_changed()

    def _on_contour_params_changed(self):
        self.canvas.set_contour_params(
            use_canny=self.rdoAnnCanny.isChecked(),
            threshold=self.sliderAnnThreshold.value(),
            canny_low=self.sliderAnnCannyLow.value(),
            canny_high=self.sliderAnnCannyHigh.value(),
            min_area=self.sliderAnnMinArea.value(),
        )

    def _on_pending_contour_changed(self, has_contour: bool):
        self.btnAddAnnotation.setEnabled(has_contour)
        self.btnDiscardAnnotation.setEnabled(has_contour)
        self.lblContourStatus.setText(
            "Contour selected — click Add Annotation."
            if has_contour
            else "Adjust the threshold until the piece's outline looks right, then click it."
        )

    # ── annotation helpers ────────────────────────────────────

    def current_class_id(self) -> int:
        row = self.lstClasses.currentRow()
        return row if row >= 0 else 0

    def class_names(self) -> list[str]:
        return [
            self.lstClasses.item(i).text()
            for i in range(self.lstClasses.count())
        ]

    def refresh_annotations_list(self):
        self.lstAnnotations.clear()
        names = self.class_names()
        for class_id, points in self.canvas.get_annotations():
            label = names[class_id] if class_id < len(names) else str(class_id)
            self.lstAnnotations.addItem(f"{label}  ({len(points)} pts)")

    # ── backend helpers ───────────────────────────────────────

    def training_backend(self) -> str:
        """Returns 'local' | 'modal' | 'colab'."""
        if self.rdoModal.isChecked():
            return "modal"
        if self.rdoColab.isChecked():
            return "colab"
        return "local"

    def _on_backend_changed(self):
        backend = self.training_backend()

        hints = {
            "local": "Trains on this machine using CPU. No internet required.",
            "modal": (
                "Trains on Modal cloud GPU (A10G, ~$1.10/hr).\n"
                "One-time setup:  pip install modal  then  modal setup"
            ),
            "colab": (
                "Exports dataset.zip + a pre-configured Colab notebook.\n"
                "Open the notebook in Google Colab, run all cells, download best.pt."
            ),
        }
        self.lblBackendHint.setText(hints[backend])

        # Show/hide the correct action buttons
        is_colab = backend == "colab"
        self.btnStartTraining.setVisible(not is_colab)
        self.btnExportColab.setVisible(is_colab)

    # ── training helpers ──────────────────────────────────────

    def selected_model_name(self) -> str:
        return self.cmbModel.currentData()

    def epochs(self) -> int:
        return self.sliderEpochs.value()

    def val_split(self) -> float:
        return self.sliderValSplit.value() / 100.0

    def dataset_path(self) -> str:
        return self.lineDatasetPath.text().strip()

    def output_dir(self) -> str:
        return self.lineOutputDir.text().strip()

    def append_log(self, text: str):
        self.logTraining.append(text)

    def set_training_progress(self, current: int, total: int, map50: float, loss: float):
        self.progressTraining.setMaximum(total)
        self.progressTraining.setValue(current)
        self.lblTrainingStatus.setText(
            f"Epoch {current}/{total}  —  mAP50: {map50:.3f}  loss: {loss:.3f}"
        )

    def set_training_finished(self, model_path: str):
        self.btnStartTraining.setEnabled(True)
        self.lblModelPath.setText(f"Model saved: {model_path}")
        self.btnOpenModelFolder.setVisible(True)
        self.lblTrainingStatus.setText("Training complete.")

    def set_training_failed(self, message: str):
        self.btnStartTraining.setEnabled(True)
        self.lblTrainingStatus.setText(f"Error: {message}")

    def set_colab_export_done(self, export_dir: str):
        """Called when ColabExporter finishes successfully."""
        self.btnExportColab.setEnabled(True)
        self.lblTrainingStatus.setText("Export ready. Open colab_trainer.ipynb in Google Colab.")
        self.lblModelPath.setText(f"Saved to: {export_dir}")
        self.btnOpenModelFolder.setVisible(True)

    def set_colab_export_failed(self, message: str):
        self.btnExportColab.setEnabled(True)
        self.lblTrainingStatus.setText(f"Export error: {message}")

    # ──────────────────────────────────────────────────────────

    def closeEvent(self, event):
        self.view_closed.emit()
        super().closeEvent(event)
