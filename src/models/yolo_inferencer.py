"""
YoloInferencer — loads a trained best.pt and runs inference on images or frames.

Usage:
    inferencer = YoloInferencer()
    inferencer.load_model("/path/to/best.pt")

    # from file path:
    results = inferencer.predict("/path/to/image.jpg", confidence=0.25)

    # from numpy BGR frame (live camera):
    results = inferencer.predict_frame(frame, confidence=0.25)

    # results: list of (class_id, class_name, confidence, cx, cy, w, h)
    #          all coordinates are YOLO-normalized (0.0 – 1.0)
"""


class YoloInferencer:

    def __init__(self):
        self._model = None
        self._model_path: str = ""

    # ── public API ────────────────────────────────────────────

    def load_model(self, model_path: str):
        """Loads a .pt weights file. Raises RuntimeError on failure."""
        try:
            from ultralytics import YOLO
            self._model = YOLO(model_path)
            self._model_path = model_path
        except ImportError:
            raise RuntimeError(
                "ultralytics not installed.\nRun: pip install ultralytics"
            )
        except Exception as exc:
            self._model = None
            self._model_path = ""
            raise RuntimeError(f"Failed to load model: {exc}") from exc

    def is_loaded(self) -> bool:
        return self._model is not None

    def model_path(self) -> str:
        return self._model_path

    def predict(
        self,
        image_path: str,
        confidence: float = 0.25,
    ) -> list[tuple[int, str, float, float, float, float, float]]:
        """
        Runs inference on image_path.

        Returns a list of detections:
            (class_id, class_name, confidence, cx, cy, w, h)
            Coordinates are YOLO-normalized (0.0 – 1.0).

        Raises RuntimeError if no model is loaded.
        """
        if not self.is_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")

        results = self._model.predict(
            source=image_path,
            conf=confidence,
            verbose=False,
        )

        detections = []
        for result in results:
            names = result.names  # {class_id: class_name}
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf   = float(box.conf[0].item())
                # xywhn = normalized cx, cy, w, h
                xywhn  = box.xywhn[0].tolist()
                cx, cy, w, h = xywhn
                name   = names.get(cls_id, str(cls_id))
                detections.append((cls_id, name, conf, cx, cy, w, h))

        return detections

    def predict_frame(
        self,
        frame,  # numpy BGR ndarray from cv2
        confidence: float = 0.25,
    ) -> list[tuple[int, str, float, float, float, float, float]]:
        """
        Runs inference directly on a numpy BGR frame (no disk I/O).
        Ultralytics accepts numpy arrays natively — ideal for live camera feed.

        Returns the same format as predict():
            (class_id, class_name, confidence, cx, cy, w, h)  normalized.
        """
        if not self.is_loaded():
            raise RuntimeError("No model loaded. Call load_model() first.")

        results = self._model.predict(
            source=frame,
            conf=confidence,
            verbose=False,
        )

        detections = []
        for result in results:
            names = result.names
            if result.boxes is None:
                continue
            for box in result.boxes:
                cls_id = int(box.cls[0].item())
                conf   = float(box.conf[0].item())
                xywhn  = box.xywhn[0].tolist()
                cx, cy, w, h = xywhn
                name   = names.get(cls_id, str(cls_id))
                detections.append((cls_id, name, conf, cx, cy, w, h))

        return detections
