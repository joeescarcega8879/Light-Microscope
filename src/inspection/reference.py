"""Persistent golden-reference sets: images + ROIs + inspection parameters per product."""
from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from .engine import InspectionParams, Roi
from .imageio import read_image, write_image

DEFAULT_ROOT = Path.home() / ".light_microscope" / "references"
_META = "reference.json"
_VERSION = 1


def safe_name(name: str) -> str:
    cleaned = re.sub(r"[^\w .-]", "_", name.strip(), flags=re.UNICODE).strip(" .")
    if not cleaned:
        raise ValueError("Reference name cannot be empty.")
    return cleaned


@dataclass
class ReferenceSet:
    name: str
    image_paths: list[Path] = field(default_factory=list)
    rois: list[Roi] = field(default_factory=list)
    params: InspectionParams = field(default_factory=InspectionParams)

    def load_images(self) -> list[np.ndarray]:
        imgs = [read_image(p) for p in self.image_paths]
        return [i for i in imgs if i is not None]


class ReferenceStore:
    def __init__(self, root: Optional[Path] = None):
        self.root = Path(root) if root else DEFAULT_ROOT

    def _dir(self, name: str) -> Path:
        return self.root / safe_name(name)

    def list_names(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted((d.name for d in self.root.iterdir() if (d / _META).is_file()),
                      key=str.lower)

    def exists(self, name: str) -> bool:
        return (self._dir(name) / _META).is_file()

    def create(self, name: str, images: list[np.ndarray],
               params: Optional[InspectionParams] = None,
               rois: Optional[list[Roi]] = None) -> ReferenceSet:
        if not images:
            raise ValueError("A reference needs at least one image.")
        d = self._dir(name)
        if (d / _META).exists():
            raise FileExistsError(f"Reference '{safe_name(name)}' already exists.")
        d.mkdir(parents=True, exist_ok=True)
        ref = ReferenceSet(safe_name(name), [], list(rois or []), params or InspectionParams())
        for img in images:
            self._write_image(d, ref, img)
        self.save_settings(ref)
        return ref

    def add_image(self, ref: ReferenceSet, img: np.ndarray) -> Path:
        path = self._write_image(self._dir(ref.name), ref, img)
        self.save_settings(ref)
        return path

    def remove_image(self, ref: ReferenceSet, index: int):
        if len(ref.image_paths) <= 1:
            raise ValueError("A reference must keep at least one image.")
        path = ref.image_paths.pop(index)
        path.unlink(missing_ok=True)
        self.save_settings(ref)

    def _write_image(self, d: Path, ref: ReferenceSet, img: np.ndarray) -> Path:
        n = 1
        while (d / f"golden_{n:03d}.png").exists():
            n += 1
        path = d / f"golden_{n:03d}.png"
        if not write_image(path, img):
            raise OSError(f"Could not write {path}")
        ref.image_paths.append(path)
        return path

    def save_settings(self, ref: ReferenceSet):
        meta = {
            "version": _VERSION,
            "images": [p.name for p in ref.image_paths],
            "rois": [r.to_dict() for r in ref.rois],
            "params": ref.params.to_dict(),
        }
        (self._dir(ref.name) / _META).write_text(json.dumps(meta, indent=2), encoding="utf-8")

    def load(self, name: str) -> ReferenceSet:
        d = self._dir(name)
        meta_path = d / _META
        if not meta_path.is_file():
            raise FileNotFoundError(f"Reference '{name}' not found.")
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        paths = [d / n for n in meta.get("images", []) if (d / n).is_file()]
        return ReferenceSet(
            name=d.name,
            image_paths=paths,
            rois=[Roi.from_dict(r) for r in meta.get("rois", [])],
            params=InspectionParams.from_dict(meta.get("params", {})),
        )

    def delete(self, name: str):
        d = self._dir(name)
        if (d / _META).is_file():
            shutil.rmtree(d)
