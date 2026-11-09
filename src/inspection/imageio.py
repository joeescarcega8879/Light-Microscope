from pathlib import Path
from typing import Optional

import cv2
import numpy as np

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}


def read_image(path) -> Optional[np.ndarray]:
    """cv2.imread that also works with non-ASCII paths. Returns BGR or None."""
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        if data.size == 0:
            return None
        return cv2.imdecode(data, cv2.IMREAD_COLOR)
    except OSError:
        return None


def write_image(path, img: np.ndarray) -> bool:
    ext = Path(path).suffix or ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        return False
    buf.tofile(str(path))
    return True


def list_images(folder) -> list[Path]:
    """Image files directly inside `folder`, sorted by name (case-insensitive)."""
    p = Path(folder)
    if not p.is_dir():
        return []
    return sorted((f for f in p.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS),
                  key=lambda f: f.name.lower())
