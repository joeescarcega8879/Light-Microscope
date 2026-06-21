import os
from pathlib import Path
from PyQt6.QtCore import QObject
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from ..models.yolo_trainer import YoloTrainer
from ..utils.yolo_utils import YoloUtils


class YoloStudioPresenter(QObject):
    def __init__(self, view):
        super().__init__()
        self.view = view
        self._image_paths: list[str] = []
        self._current_index: int = -1
        self._folder_path: str = ""
        self._trainer: YoloTrainer | None = None
        self._connect_signals()

    def _connect_signals(self):
        v = self.view

        # annotation tab
        v.btnLoadFolder.clicked.connect(self._load_folder)
        v.btnPrev.clicked.connect(self._prev_image)
        v.btnNext.clicked.connect(self._next_image)
        v.btnSaveLabels.clicked.connect(self._save_current_labels)
        v.btnAddClass.clicked.connect(self._add_class)
        v.lineClassName.returnPressed.connect(self._add_class)
        v.btnRemoveClass.clicked.connect(self._remove_class)
        v.lstClasses.currentRowChanged.connect(self._on_class_selected)
        v.btnDeleteAnnotation.clicked.connect(self._delete_annotation)
        v.btnApplyToAll.clicked.connect(self._apply_to_all)
        v.canvas.annotation_added.connect(lambda *_: self._on_annotation_changed())

        # training tab
        v.btnBrowseDataset.clicked.connect(self._browse_dataset)
        v.btnBrowseOutput.clicked.connect(self._browse_output)
        v.btnStartTraining.clicked.connect(self._start_training)
        v.btnOpenModelFolder.clicked.connect(self._open_model_folder)

    # ── annotation ────────────────────────────────────────────

    def _load_folder(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Select Image Folder")
        if not folder:
            return
        self._folder_path = folder
        exts = {".jpg", ".jpeg", ".png", ".bmp"}
        self._image_paths = sorted(
            str(p) for p in Path(folder).iterdir()
            if p.suffix.lower() in exts
        )
        if not self._image_paths:
            return

        # Load persisted class names
        names = YoloUtils.load_class_names(folder)
        self.view.lstClasses.clear()
        for name in names:
            self.view.lstClasses.addItem(name)
        if self.view.lstClasses.count():
            self.view.lstClasses.setCurrentRow(0)

        self.view.btnSaveLabels.setEnabled(True)
        self.view.btnPrev.setEnabled(True)
        self.view.btnNext.setEnabled(True)
        self._current_index = 0
        self._load_image(0)

        # pre-fill training dataset path
        if not self.view.lineDatasetPath.text():
            self.view.lineDatasetPath.setText(folder)

    def _load_image(self, index: int):
        path = self._image_paths[index]
        pixmap = QPixmap(path)
        self.view.canvas.set_image(pixmap)
        self.view.lblCurrentFile.setText(Path(path).name)
        self.view.lblImageCounter.setText(
            f"{index + 1} / {len(self._image_paths)}"
        )

        # Load existing labels for this image
        label_path = str(Path(path).with_suffix(".txt"))
        annotations = YoloUtils.load_labels(label_path)
        self.view.canvas.set_annotations(annotations)
        self.view.canvas.set_class_names(self.view.class_names())
        self.view.refresh_annotations_list()
        self._update_apply_button()

    def _prev_image(self):
        if self._current_index > 0:
            self._save_current_labels()
            self._current_index -= 1
            self._load_image(self._current_index)

    def _next_image(self):
        if self._current_index < len(self._image_paths) - 1:
            self._save_current_labels()
            self._current_index += 1
            self._load_image(self._current_index)

    def _save_current_labels(self):
        if self._current_index < 0 or not self._image_paths:
            return
        path = self._image_paths[self._current_index]
        label_path = str(Path(path).with_suffix(".txt"))
        annotations = self.view.canvas.get_annotations()
        if annotations:
            YoloUtils.save_labels(annotations, label_path)
        elif os.path.exists(label_path):
            os.remove(label_path)

    def _add_class(self):
        name = self.view.lineClassName.text().strip()
        if not name:
            return
        existing = self.view.class_names()
        if name in existing:
            return
        self.view.lstClasses.addItem(name)
        self.view.lineClassName.clear()
        if self.view.lstClasses.count() == 1:
            self.view.lstClasses.setCurrentRow(0)
        self._persist_classes()
        self.view.canvas.set_class_names(self.view.class_names())

    def _remove_class(self):
        row = self.view.lstClasses.currentRow()
        if row < 0:
            return
        self.view.lstClasses.takeItem(row)
        self._persist_classes()
        self.view.canvas.set_class_names(self.view.class_names())

    def _on_class_selected(self, row: int):
        if row >= 0:
            self.view.canvas.set_active_class(row)

    def _delete_annotation(self):
        row = self.view.lstAnnotations.currentRow()
        if row >= 0:
            self.view.canvas.remove_annotation(row)
            self.view.refresh_annotations_list()
            self._update_apply_button()

    def _on_annotation_changed(self):
        self.view.refresh_annotations_list()
        self._update_apply_button()

    def _update_apply_button(self):
        has_folder = len(self._image_paths) > 0
        has_annotations = len(self.view.canvas.get_annotations()) > 0
        self.view.btnApplyToAll.setEnabled(has_folder and has_annotations)

    def _apply_to_all(self):
        annotations = self.view.canvas.get_annotations()
        if not annotations:
            return

        n = len(self._image_paths)
        reply = QMessageBox.question(
            self.view,
            "Apply to all",
            f"This will overwrite labels for all {n} images in the folder.\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        for path in self._image_paths:
            label_path = str(Path(path).with_suffix(".txt"))
            YoloUtils.save_labels(annotations, label_path)

        self.view.lblCurrentFile.setText(f"Labels applied to {n} images.")

    def _persist_classes(self):
        if self._folder_path:
            YoloUtils.save_class_names(self.view.class_names(), self._folder_path)
        # Update training tab summary
        names = self.view.class_names()
        self.view.lblClassesSummary.setText(
            ", ".join(names) if names else "—"
        )

    # ── training ──────────────────────────────────────────────

    def _browse_dataset(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Select Dataset Folder")
        if folder:
            self.view.lineDatasetPath.setText(folder)
            names = YoloUtils.load_class_names(folder)
            self.view.lblClassesSummary.setText(
                ", ".join(names) if names else "No classes.txt found"
            )

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self.view, "Select Output Folder")
        if folder:
            self.view.lineOutputDir.setText(folder)

    def _start_training(self):
        dataset_dir = self.view.dataset_path()
        output_dir = self.view.output_dir()

        if not dataset_dir or not os.path.isdir(dataset_dir):
            self.view.lblTrainingStatus.setText("Error: select a valid dataset folder.")
            return
        if not output_dir:
            output_dir = os.path.join(dataset_dir, "models")
            self.view.lineOutputDir.setText(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        class_names = YoloUtils.load_class_names(dataset_dir)
        if not class_names:
            self.view.lblTrainingStatus.setText(
                "Error: no classes.txt found. Add classes in the Annotate tab first."
            )
            return

        try:
            yaml_path = YoloUtils.prepare_dataset(
                dataset_dir, class_names, self.view.val_split()
            )
        except ValueError as exc:
            self.view.lblTrainingStatus.setText(f"Error: {exc}")
            return

        self.view.logTraining.clear()
        self.view.progressTraining.setValue(0)
        self.view.progressTraining.setMaximum(self.view.epochs())
        self.view.btnStartTraining.setEnabled(False)
        self.view.btnOpenModelFolder.setVisible(False)
        self.view.lblModelPath.setText("")

        self._trainer = YoloTrainer(
            data_yaml=yaml_path,
            model_name=self.view.selected_model_name(),
            epochs=self.view.epochs(),
            output_dir=output_dir,
        )
        self._trainer.epoch_ended.connect(self.view.set_training_progress)
        self._trainer.log_message.connect(self.view.append_log)
        self._trainer.training_finished.connect(self.view.set_training_finished)
        self._trainer.training_failed.connect(self.view.set_training_failed)
        self._trainer.start()

    def _open_model_folder(self):
        output_dir = self.view.output_dir()
        run_dir = os.path.join(output_dir, "run")
        folder = run_dir if os.path.isdir(run_dir) else output_dir
        import subprocess
        subprocess.Popen(["xdg-open", folder])
