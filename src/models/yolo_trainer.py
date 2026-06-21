from PyQt6.QtCore import QThread, pyqtSignal


class YoloTrainer(QThread):
    epoch_ended = pyqtSignal(int, int, float, float)  # current, total, mAP50, loss
    training_finished = pyqtSignal(str)               # path to best.pt
    training_failed = pyqtSignal(str)                 # error message
    log_message = pyqtSignal(str)

    def __init__(self, data_yaml: str, model_name: str, epochs: int, output_dir: str):
        super().__init__()
        self._data_yaml = data_yaml
        self._model_name = model_name   # 'yolov8n' | 'yolov8s'
        self._epochs = epochs
        self._output_dir = output_dir

    def run(self):
        try:
            from ultralytics import YOLO

            model = YOLO(f"{self._model_name}.pt")
            total = self._epochs

            def _on_epoch_end(trainer):
                epoch = trainer.epoch + 1
                metrics = trainer.metrics or {}
                map50 = float(metrics.get("metrics/mAP50(B)", 0.0))
                loss_val = trainer.loss
                loss = float(loss_val.item()) if hasattr(loss_val, "item") else float(loss_val)
                self.epoch_ended.emit(epoch, total, map50, loss)
                self.log_message.emit(
                    f"Epoch {epoch}/{total} — mAP50: {map50:.3f}  loss: {loss:.3f}"
                )

            model.add_callback("on_train_epoch_end", _on_epoch_end)

            model.train(
                data=self._data_yaml,
                epochs=self._epochs,
                imgsz=640,
                device="cpu",
                project=self._output_dir,
                name="run",
                exist_ok=True,
                verbose=False,
            )

            import os
            best = os.path.join(self._output_dir, "run", "weights", "best.pt")
            if os.path.exists(best):
                self.training_finished.emit(best)
            else:
                self.training_failed.emit("best.pt not found after training.")

        except ImportError:
            self.training_failed.emit(
                "ultralytics not installed.\nRun: pip install ultralytics"
            )
        except Exception as exc:
            self.training_failed.emit(str(exc))
