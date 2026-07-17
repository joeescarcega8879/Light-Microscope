"""
ColabExporter — Prepares a self-contained export package for Google Colab training.

Output (saved to a user-chosen folder):
    colab_export/
    ├── dataset.zip          — all images + .txt labels + classes.txt
    └── colab_trainer.ipynb  — pre-configured notebook (model, epochs, val_split injected)

Usage from the presenter:
    from ..models.colab_exporter import ColabExporter

    ok, msg = ColabExporter.export(
        dataset_dir  = "/path/to/annotated/images",
        output_dir   = "/path/chosen/by/user",
        model_name   = "yolov8n",
        epochs       = 50,
        val_split    = 0.2,
    )
"""
import json
import os
import zipfile


class ColabExporter:

    # ── public API ────────────────────────────────────────────

    @staticmethod
    def export(
        dataset_dir: str,
        output_dir: str,
        model_name: str,
        epochs: int,
        val_split: float,
    ) -> tuple[bool, str]:
        """
        Creates the export folder with dataset.zip and colab_trainer.ipynb.
        Returns (success: bool, message: str).
        """
        try:
            export_dir = os.path.join(output_dir, "colab_export")
            os.makedirs(export_dir, exist_ok=True)

            # 1. Zip the dataset
            zip_path = os.path.join(export_dir, "dataset.zip")
            ColabExporter._zip_dataset(dataset_dir, zip_path)

            # 2. Generate the notebook
            nb_path = os.path.join(export_dir, "colab_trainer.ipynb")
            ColabExporter._write_notebook(
                nb_path,
                model_name=model_name,
                epochs=epochs,
                val_split=val_split,
            )

            return True, export_dir

        except Exception as exc:
            return False, str(exc)

    # ── dataset zip ───────────────────────────────────────────

    @staticmethod
    def _zip_dataset(dataset_dir: str, zip_path: str):
        valid_exts = {".jpg", ".jpeg", ".png", ".bmp", ".txt"}
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(dataset_dir):
                ext = os.path.splitext(filename)[1].lower()
                # include images, label .txt files, and classes.txt
                if ext in valid_exts or filename == "classes.txt":
                    full = os.path.join(dataset_dir, filename)
                    if os.path.isfile(full):
                        zf.write(full, filename)

    # ── notebook generation ───────────────────────────────────

    @staticmethod
    def _write_notebook(
        path: str,
        model_name: str,
        epochs: int,
        val_split: float,
    ):
        nb = ColabExporter._build_notebook(model_name, epochs, val_split)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(nb, f, indent=1, ensure_ascii=False)

    @staticmethod
    def _build_notebook(model_name: str, epochs: int, val_split: float) -> dict:
        """Builds a minimal Jupyter notebook dict (nbformat 4)."""

        def code(src: str) -> dict:
            return {
                "cell_type": "code",
                "execution_count": None,
                "metadata": {},
                "outputs": [],
                "source": src,
            }

        def markdown(src: str) -> dict:
            return {
                "cell_type": "markdown",
                "metadata": {},
                "source": src,
            }

        cells = [
            markdown(
                "# YOLOv8 Training — Light Microscope App\n"
                "Generated automatically. Run all cells with **Runtime → Run all** (`Ctrl+F9`).\n\n"
                "**Before running:**\n"
                "1. Upload `dataset.zip` to your Google Drive.\n"
                "2. Set `DRIVE_ZIP_PATH` in the Configuration cell to point to it.\n"
                "3. Set `OUTPUT_DIR` where you want `best.pt` saved."
            ),

            # ── Cell 1: install ──────────────────────────────
            code("!pip install ultralytics --quiet"),

            # ── Cell 2: mount Drive ──────────────────────────
            code(
                "from google.colab import drive\n"
                "drive.mount('/content/drive')"
            ),

            # ── Cell 3: configuration (pre-filled) ───────────
            code(
                "# ── Configuration ──────────────────────────────────────\n"
                "# Path to the dataset.zip you uploaded to Google Drive:\n"
                f"DRIVE_ZIP_PATH = '/content/drive/MyDrive/dataset.zip'\n\n"
                "# Where to save the trained model inside Drive:\n"
                f"OUTPUT_DIR     = '/content/drive/MyDrive/yolo_output'\n\n"
                "# Training parameters (pre-filled from the app):\n"
                f"MODEL_NAME     = '{model_name}'\n"
                f"EPOCHS         = {epochs}\n"
                f"VAL_SPLIT      = {val_split}\n"
            ),

            # ── Cell 4: extract dataset ───────────────────────
            code(
                "import zipfile, os, shutil, random, yaml\n\n"
                "DATASET_DIR = '/content/dataset'\n"
                "os.makedirs(DATASET_DIR, exist_ok=True)\n\n"
                "print('Extracting dataset...')\n"
                "with zipfile.ZipFile(DRIVE_ZIP_PATH) as zf:\n"
                "    zf.extractall(DATASET_DIR)\n"
                "print(f'Extracted {len(os.listdir(DATASET_DIR))} files.')"
            ),

            # ── Cell 5: prepare YOLO structure ───────────────
            code(
                "# Build train/val split and data.yaml\n"
                "images = [f for f in os.listdir(DATASET_DIR)\n"
                "          if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp'))]\n"
                "random.shuffle(images)\n"
                "val_n      = max(1, int(len(images) * VAL_SPLIT))\n"
                "val_imgs   = images[:val_n]\n"
                "train_imgs = images[val_n:]\n\n"
                "YOLO_DIR = '/content/yolo_dataset'\n"
                "for split, imgs in [('train', train_imgs), ('val', val_imgs)]:\n"
                "    img_dir = f'{YOLO_DIR}/{split}/images'\n"
                "    lbl_dir = f'{YOLO_DIR}/{split}/labels'\n"
                "    os.makedirs(img_dir, exist_ok=True)\n"
                "    os.makedirs(lbl_dir, exist_ok=True)\n"
                "    for img in imgs:\n"
                "        shutil.copy(f'{DATASET_DIR}/{img}', img_dir)\n"
                "        lbl = os.path.splitext(img)[0] + '.txt'\n"
                "        if os.path.exists(f'{DATASET_DIR}/{lbl}'):\n"
                "            shutil.copy(f'{DATASET_DIR}/{lbl}', lbl_dir)\n\n"
                "with open(f'{DATASET_DIR}/classes.txt') as f:\n"
                "    class_names = [l.strip() for l in f if l.strip()]\n\n"
                "data_yaml = {\n"
                "    'path': YOLO_DIR,\n"
                "    'train': 'train/images',\n"
                "    'val':   'val/images',\n"
                "    'nc':    len(class_names),\n"
                "    'names': class_names,\n"
                "}\n"
                "YAML_PATH = f'{YOLO_DIR}/data.yaml'\n"
                "with open(YAML_PATH, 'w') as f:\n"
                "    yaml.dump(data_yaml, f, default_flow_style=False)\n\n"
                "print(f'Classes: {class_names}')\n"
                "print(f'Train: {len(train_imgs)} images  |  Val: {len(val_imgs)} images')"
            ),

            # ── Cell 6: train ─────────────────────────────────
            code(
                "from ultralytics import YOLO\n\n"
                "model = YOLO(f'{MODEL_NAME}.pt')\n"
                "model.train(\n"
                "    data=YAML_PATH,\n"
                "    epochs=EPOCHS,\n"
                "    imgsz=640,\n"
                "    device=0,  # GPU\n"
                "    project='/content/output',\n"
                "    name='run',\n"
                "    exist_ok=True,\n"
                ")\n"
                "print('Training complete.')"
            ),

            # ── Cell 7: save best.pt to Drive ────────────────
            code(
                "import shutil\n\n"
                "best_src = '/content/output/run/weights/best.pt'\n"
                "os.makedirs(OUTPUT_DIR, exist_ok=True)\n"
                "dest = f'{OUTPUT_DIR}/best.pt'\n"
                "shutil.copy(best_src, dest)\n"
                "print(f'Model saved to Drive: {dest}')\n\n"
                "# Direct download to your browser (optional):\n"
                "from google.colab import files\n"
                "files.download(best_src)"
            ),
        ]

        return {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python", "version": "3.10.0"},
                "colab": {"provenance": []},
            },
            "cells": cells,
        }
