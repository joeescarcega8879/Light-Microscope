import numpy as np
from PyQt6.QtGui import QImage, QPixmap

from ..inspection.engine import to_bgr


def bgr_to_qimage(img: np.ndarray) -> QImage:
    img = np.ascontiguousarray(to_bgr(img))
    h, w, ch = img.shape
    return QImage(img.data, w, h, ch * w, QImage.Format.Format_BGR888).copy()


def bgr_to_qpixmap(img: np.ndarray) -> QPixmap:
    return QPixmap.fromImage(bgr_to_qimage(img))
