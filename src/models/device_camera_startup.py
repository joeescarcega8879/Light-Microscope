import cv2
import platform
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QThread, pyqtSignal

from ..utils.image_utils import TypeCapture, TypePlatform


class DeviceCameraStartup(QThread):
    change_pixmap_signal = pyqtSignal(QPixmap)
    raw_frame_signal = pyqtSignal(object)

    def __init__(self, camera_index: int, type_capture: TypeCapture):
        super().__init__()
        self.camera_index = camera_index
        self.type_capture = type_capture
        self._run_flag = True

    def stop(self):
        self._run_flag = False
        self.wait()

    def run(self):
        os_name = platform.system()
        cap = None
        try:
            if os_name == TypePlatform.Windows.value:
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1368)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
            elif os_name == TypePlatform.Linux.value:
                cap = cv2.VideoCapture(self.camera_index, cv2.CAP_V4L2)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1368)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                
            else:
                cap = cv2.VideoCapture(self.camera_index)

            if cap is None or not cap.isOpened():
                return

            cap.set(cv2.CAP_PROP_FPS, 60)

            while self._run_flag:
                ret, cv_img = cap.read()
                if ret:
                    pixmap = self._convert_to_pixmap(cv_img)
                    self.change_pixmap_signal.emit(pixmap)
                    self.raw_frame_signal.emit(cv_img)
        finally:
            if cap is not None:
                cap.release()

    @staticmethod
    def _convert_to_pixmap(cv_img) -> QPixmap:
        rgb_image = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        q_image = QImage(rgb_image.data, w, h, ch * w, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(q_image)
