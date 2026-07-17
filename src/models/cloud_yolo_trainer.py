"""
CloudYoloTrainer — QThread that trains YOLOv8 on Modal cloud GPU.

Emits the same signals as YoloTrainer so the view/presenter need no changes:
    epoch_ended      (current: int, total: int, map50: float, loss: float)
    training_finished(path: str)   — local path to downloaded best.pt
    training_failed  (msg: str)
    log_message      (text: str)

Workflow:
    1. Verify modal CLI is installed and authenticated
    2. Zip the source dataset_dir to a temp file
    3. modal volume put  →  upload zip to Modal data Volume
    4. modal run modal_trainer.py  →  train on A10G (subprocess, parse stdout)
    5. modal volume get  →  download best.pt to local output_dir
    6. Emit training_finished(local_best_pt)
"""
import os
import subprocess
import tempfile
import time
import zipfile

from PyQt6.QtCore import QThread, pyqtSignal

# Names must match those declared in modal_trainer.py
_DATA_VOLUME    = "yolo-microscope-data"
_WEIGHTS_VOLUME = "yolo-microscope-weights"


class CloudYoloTrainer(QThread):
    epoch_ended       = pyqtSignal(int, int, float, float)  # current, total, mAP50, loss
    training_finished = pyqtSignal(str)                     # local path to best.pt
    training_failed   = pyqtSignal(str)                     # error message
    log_message       = pyqtSignal(str)

    def __init__(
        self,
        dataset_dir: str,
        model_name: str,
        epochs: int,
        val_split: float,
        output_dir: str,
    ):
        super().__init__()
        self._dataset_dir = dataset_dir
        self._model_name  = model_name
        self._epochs      = epochs
        self._val_split   = val_split
        self._output_dir  = output_dir

    # ── entry point ───────────────────────────────────────────

    def run(self):
        try:
            run_name = f"run_{int(time.time())}"

            self._check_modal()
            zip_path = self._zip_dataset()
            self._upload_dataset(zip_path)
            self._run_training(run_name)
            local_best = self._download_model(run_name)
            self.training_finished.emit(local_best)

        except Exception as exc:
            self.training_failed.emit(str(exc))
        finally:
            # Clean up temp zip if it still exists
            try:
                if "zip_path" in dir() and os.path.exists(zip_path):
                    os.remove(zip_path)
            except Exception:
                pass

    # ── step 1: modal check ───────────────────────────────────

    def _check_modal(self):
        self.log_message.emit("[Cloud] Checking Modal installation...")

        result = subprocess.run(
            ["modal", "--version"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "Modal CLI not found.\n"
                "Install it with:  pip install modal\n"
                "Then run:         modal setup"
            )

        self.log_message.emit(f"[Cloud] Modal {result.stdout.strip()} found.")
        self.log_message.emit("[Cloud] Checking authentication...")

        auth = subprocess.run(
            ["modal", "token", "check"],
            capture_output=True, text=True,
        )
        if auth.returncode != 0:
            raise RuntimeError(
                "Modal is not authenticated.\n"
                "Run this command once:  modal setup"
            )

        self.log_message.emit("[Cloud] Authentication OK.")

    # ── step 2: zip dataset ───────────────────────────────────

    def _zip_dataset(self) -> str:
        self.log_message.emit("[Cloud] Compressing dataset...")
        zip_path = os.path.join(tempfile.gettempdir(), "yolo_microscope_upload.zip")

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _dirs, files in os.walk(self._dataset_dir):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    arcname   = os.path.relpath(full_path, self._dataset_dir)
                    zf.write(full_path, arcname)

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        self.log_message.emit(f"[Cloud] Dataset compressed: {size_mb:.1f} MB")
        return zip_path

    # ── step 3: upload to Modal Volume ────────────────────────

    def _upload_dataset(self, zip_path: str):
        self.log_message.emit(f"[Cloud] Uploading to Modal Volume '{_DATA_VOLUME}'...")

        result = subprocess.run(
            ["modal", "volume", "put", _DATA_VOLUME, zip_path, "/dataset.zip"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Dataset upload failed:\n{result.stderr or result.stdout}"
            )

        self.log_message.emit("[Cloud] Upload complete.")

    # ── step 4: run training on cloud ─────────────────────────

    def _run_training(self, run_name: str):
        self.log_message.emit(
            f"[Cloud] Starting training on Modal A10G GPU (run: {run_name})..."
        )

        # Resolve the absolute path to modal_trainer.py
        modal_script = os.path.join(
            os.path.dirname(__file__), "modal_trainer.py"
        )

        cmd = [
            "modal", "run", modal_script,
            "--model-name", self._model_name,
            "--epochs",     str(self._epochs),
            "--val-split",  str(self._val_split),
            "--run-name",   run_name,
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        for raw_line in proc.stdout:
            line = raw_line.rstrip()
            if not line:
                continue

            self.log_message.emit(line)

            # Parse progress: "[EPOCH] 5/50 mAP50=0.6543 loss=0.1234"
            if line.startswith("[EPOCH]"):
                self._parse_epoch_line(line)

        proc.wait()
        if proc.returncode != 0:
            raise RuntimeError(
                "Modal training process exited with an error. "
                "Check the log above for details."
            )

        self.log_message.emit("[Cloud] Training finished on cloud.")

    def _parse_epoch_line(self, line: str):
        # Format: "[EPOCH] {epoch}/{total} mAP50={map50} loss={loss}"
        try:
            parts   = line.split()           # ["[EPOCH]", "5/50", "mAP50=...", "loss=..."]
            epoch, total = map(int, parts[1].split("/"))
            map50   = float(parts[2].split("=")[1])
            loss    = float(parts[3].split("=")[1])
            self.epoch_ended.emit(epoch, total, map50, loss)
        except (IndexError, ValueError):
            pass  # Malformed line — skip silently

    # ── step 5: download best.pt ──────────────────────────────

    def _download_model(self, run_name: str) -> str:
        os.makedirs(self._output_dir, exist_ok=True)
        local_best = os.path.join(self._output_dir, "best.pt")

        # In-volume path matches modal_trainer.py: project=/weights/{run_name}, name="weights"
        # ultralytics saves to: /weights/{run_name}/weights/weights/best.pt
        # In the volume that maps to: {run_name}/weights/weights/best.pt
        volume_path = f"{run_name}/weights/weights/best.pt"

        self.log_message.emit(
            f"[Cloud] Downloading best.pt from Modal Volume '{_WEIGHTS_VOLUME}'..."
        )

        result = subprocess.run(
            ["modal", "volume", "get", _WEIGHTS_VOLUME, volume_path, local_best],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Model download failed:\n{result.stderr or result.stdout}"
            )

        self.log_message.emit(f"[Cloud] Model saved to: {local_best}")
        return local_best
