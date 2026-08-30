import os
import random
import shutil
from pathlib import Path

import yaml


class YoloUtils:

    @staticmethod
    def load_labels(label_path: str) -> list[tuple]:
        """Load YOLO-segmentation .txt labels → list of (class_id, points).

        Each line is `class_id x1 y1 x2 y2 ... xn yn` (normalized polygon,
        n >= 3 points).
        """
        labels = []
        if os.path.exists(label_path):
            with open(label_path) as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 7 and len(parts) % 2 == 1:
                        class_id = int(parts[0])
                        coords = [float(v) for v in parts[1:]]
                        points = list(zip(coords[0::2], coords[1::2]))
                        labels.append((class_id, points))
        return labels

    @staticmethod
    def save_labels(labels: list[tuple], label_path: str):
        """Save list of (class_id, points) to YOLO-segmentation .txt format."""
        with open(label_path, "w") as f:
            for class_id, points in labels:
                coords = " ".join(f"{x:.6f} {y:.6f}" for x, y in points)
                f.write(f"{class_id} {coords}\n")

    @staticmethod
    def prepare_dataset(
        source_dir: str,
        class_names: list[str],
        val_split: float = 0.2,
    ) -> str:
        """
        Copies annotated images from source_dir into a YOLO dataset structure
        inside source_dir/yolo_dataset/.  Returns path to data.yaml.
        """
        source = Path(source_dir)
        dataset = source / "yolo_dataset"

        for split in ("train", "val"):
            (dataset / "images" / split).mkdir(parents=True, exist_ok=True)
            (dataset / "labels" / split).mkdir(parents=True, exist_ok=True)

        image_exts = {".jpg", ".jpeg", ".png", ".bmp"}
        annotated: list[Path] = []
        for p in source.iterdir():
            if p.suffix.lower() in image_exts:
                if (source / (p.stem + ".txt")).exists():
                    annotated.append(p)

        if not annotated:
            raise ValueError("No annotated images found in the source folder.")

        random.shuffle(annotated)
        n_val = max(1, int(len(annotated) * val_split))
        splits = {"val": annotated[:n_val], "train": annotated[n_val:]}

        for split, images in splits.items():
            for img in images:
                shutil.copy(img, dataset / "images" / split / img.name)
                lbl = source / (img.stem + ".txt")
                shutil.copy(lbl, dataset / "labels" / split / (img.stem + ".txt"))

        yaml_path = dataset / "data.yaml"
        data = {
            "path": str(dataset.resolve()),
            "train": "images/train",
            "val": "images/val",
            "nc": len(class_names),
            "names": class_names,
        }
        with open(yaml_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False)

        return str(yaml_path)

    @staticmethod
    def load_class_names(source_dir: str) -> list[str]:
        """
        Read classes.txt from source_dir if it exists.
        Returns list of class names, or empty list if not found.
        """
        path = Path(source_dir) / "classes.txt"
        if path.exists():
            with open(path) as f:
                return [line.strip() for line in f if line.strip()]
        return []

    @staticmethod
    def save_class_names(class_names: list[str], source_dir: str):
        """Persist class list to classes.txt in source_dir."""
        path = Path(source_dir) / "classes.txt"
        with open(path, "w") as f:
            for name in class_names:
                f.write(name + "\n")
