import numpy as np
from typing import Optional
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QObject

from ..utils.image_utils import ImageUtils


class ImageComparisonPresenter(QObject):
    def __init__(self, view, main_app):
        super().__init__()
        self.view = view
        self.main_app = main_app
        self._connect_signals()

    def _connect_signals(self):
        self.view.load_image_a_requested.connect(self._on_load_image_a)
        self.view.load_image_b_requested.connect(self._on_load_image_b)
        self.view.compare_images_requested.connect(self._process_images)

    def _on_load_image_a(self):
        self.view.load_image_a()

    def _on_load_image_b(self):
        self.view.load_image_b()

    def _process_images(self):
        pixmap_a: Optional[QPixmap] = self.view.get_image_a()
        pixmap_b: Optional[QPixmap] = self.view.get_image_b()

        if pixmap_a is None or pixmap_b is None:
            return

        img_a = ImageUtils.qpixmap_to_numpy(pixmap_a)
        img_b = ImageUtils.qpixmap_to_numpy(pixmap_b)
        threshold = self.view.get_threshold()

        diff, binary_mask, heatmap = ImageUtils.compute_diff(img_a, img_b, threshold)
        contour_img = ImageUtils.draw_contours(img_a, binary_mask)

        changed = int(np.count_nonzero(binary_mask))
        total = int(binary_mask.size)
        pct = (changed / total) * 100
        stats_text = f"Changed pixels: {changed:,} / {total:,}  ({pct:.1f}%)"

        self.main_app.open_comparison_result_view(diff, heatmap, contour_img, stats_text)
