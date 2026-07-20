import cv2

from ..utils.image_utils import ImageUtils


class ContourDetectionPresenter:
    def __init__(self, view):
        self.view = view
        self._image = None  # np.ndarray BGR, currently loaded image
        self._connect_signals()

    def _connect_signals(self):
        self.view.load_image_requested.connect(self._on_load_image)
        self.view.detection_params_changed.connect(self._on_params_changed)

    def _on_load_image(self):
        file_path = self.view.load_image()
        if not file_path:
            return
        self._image = cv2.imread(file_path)
        if self._image is None:
            return
        self._run_detection()

    def _on_params_changed(self):
        if self._image is None:
            return
        self._run_detection()

    def _run_detection(self):
        contour_img, contours, _ = ImageUtils.detect_contours(
            self._image,
            threshold=self.view.get_threshold(),
            use_canny=self.view.get_use_canny(),
            canny_low=self.view.get_canny_low(),
            canny_high=self.view.get_canny_high(),
            min_area=self.view.get_min_area(),
        )
        self.view.display_result(contour_img)

        total_area = sum(cv2.contourArea(c) for c in contours)
        self.view.set_stats(f"Contours: {len(contours)}   Total area: {total_area:.0f} px²")
