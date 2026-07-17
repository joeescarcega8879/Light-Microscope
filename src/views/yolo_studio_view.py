import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal, Qt, QRect, QPoint
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPixmap
)
from PyQt6.QtWidgets import QWidget, QVBoxLayout

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
    annotation_added = pyqtSignal(int, float, float, float, float)
    annotation_removed = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._annotations: list[tuple] = []   # (class_id, cx, cy, w, h)
        self._class_names: list[str] = []
        self._active_class: int = 0
        self._drawing = False
        self._start = QPoint()
        self._drag_rect = QRect()
        self.setMinimumSize(300, 300)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)

    # ── public API ────────────────────────────────────────────

    def set_image(self, pixmap: QPixmap):
        self._pixmap = pixmap
        self.update()

    def clear_image(self):
        self._pixmap = None
        self._annotations = []
        self.update()

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

    def _to_yolo(self, screen: QRect) -> tuple[float, float, float, float]:
        x0, y0, iw, ih = self._image_rect()
        x1 = max(0.0, (screen.left() - x0) / iw)
        y1 = max(0.0, (screen.top() - y0) / ih)
        x2 = min(1.0, (screen.right() - x0) / iw)
        y2 = min(1.0, (screen.bottom() - y0) / ih)
        return (x1 + x2) / 2, (y1 + y2) / 2, x2 - x1, y2 - y1

    def _to_screen(self, cx, cy, w, h) -> QRect:
        x0, y0, iw, ih = self._image_rect()
        x1 = int((cx - w / 2) * iw) + x0
        y1 = int((cy - h / 2) * ih) + y0
        x2 = int((cx + w / 2) * iw) + x0
        y2 = int((cy + h / 2) * ih) + y0
        return QRect(QPoint(x1, y1), QPoint(x2, y2))

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

            for class_id, cx, cy, w, h in self._annotations:
                color = _class_color(class_id)
                rect = self._to_screen(cx, cy, w, h)
                painter.setPen(QPen(color, 2))
                painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                painter.drawRect(rect)

                label = (
                    self._class_names[class_id]
                    if class_id < len(self._class_names)
                    else str(class_id)
                )
                bg = QColor(color)
                bg.setAlpha(200)
                text_rect = QRect(rect.left(), rect.top() - 17, len(label) * 8 + 8, 17)
                painter.fillRect(text_rect, bg)
                painter.setPen(QPen(Qt.GlobalColor.white))
                painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, label)

        # box being drawn
        if self._drawing and not self._drag_rect.isNull():
            pen = QPen(Qt.GlobalColor.yellow, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(Qt.BrushStyle.NoBrush))
            painter.drawRect(self._drag_rect)

    # ── mouse ──────────────────────────────────────────────────

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap:
            self._drawing = True
            self._start = event.pos()
            self._drag_rect = QRect(self._start, self._start)

    def mouseMoveEvent(self, event):
        if self._drawing:
            self._drag_rect = QRect(self._start, event.pos()).normalized()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._drawing:
            self._drawing = False
            rect = QRect(self._start, event.pos()).normalized()
            if rect.width() > 8 and rect.height() > 8:
                cx, cy, w, h = self._to_yolo(rect)
                if w > 0.01 and h > 0.01:
                    self._annotations.append((self._active_class, cx, cy, w, h))
                    self.annotation_added.emit(self._active_class, cx, cy, w, h)
            self._drag_rect = QRect()
            self.update()


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

        # Training — model options
        self.cmbModel.addItem("YOLOv8 Nano  (fastest, CPU-friendly)", "yolov8n")
        self.cmbModel.addItem("YOLOv8 Small (more accurate, slower)", "yolov8s")

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

        # Detect — confidence slider live label
        self.sliderConfidence.valueChanged.connect(
            lambda v: self.lblConfidence.setText(f"{v} %")
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
        for class_id, cx, cy, w, h in self.canvas.get_annotations():
            label = names[class_id] if class_id < len(names) else str(class_id)
            self.lstAnnotations.addItem(
                f"{label}  ({cx:.2f}, {cy:.2f})  {w:.2f}×{h:.2f}"
            )

    # ── detect helpers ────────────────────────────────────────

    def confidence(self) -> float:
        return self.sliderConfidence.value() / 100.0

    def set_model_loaded(self, model_path: str):
        import os
        self.lblModelLoaded.setText(os.path.basename(model_path))
        self.lblModelLoaded.setStyleSheet("color: green; font-size: 11px;")
        self.btnDetect.setEnabled(True)
        self.lblDetectStatus.setText("")

    def set_model_load_failed(self, message: str):
        self.lblModelLoaded.setText("Load failed")
        self.lblModelLoaded.setStyleSheet("color: red; font-size: 11px;")
        self.btnDetect.setEnabled(False)
        self.lblDetectStatus.setText(message)

    def set_detect_result(self, count: int):
        if count == 0:
            self.lblDetectStatus.setText("No detections found.")
        else:
            self.lblDetectStatus.setText(f"{count} detection(s) found.")

    def set_detect_failed(self, message: str):
        self.lblDetectStatus.setText(f"Error: {message}")

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
