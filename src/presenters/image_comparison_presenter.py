from typing import Optional
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import QObject

from ..inspection.engine import InspectionParams, inspect_image
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

        # A is the reference; B is aligned onto it (handles shifts, rotation and size changes).
        params = InspectionParams(threshold=self.view.get_threshold())
        res = inspect_image(img_a, img_b, params)

        lines = [
            f"Verdict: {res.verdict}  ·  {len(res.defects)} difference(s)  ·  "
            f"changed area {res.defect_area_px:,} px ({res.defect_area_pct:.2f}%)",
            f"Alignment: {res.align.method if res.align.success else 'failed'}",
        ]
        lines += res.warnings
        self.main_app.open_comparison_result_view(res.diff, res.heatmap, res.overlay, "\n".join(lines))
