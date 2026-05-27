import cv2
import time
import platform
from uuid import uuid4
from PyQt6.QtGui import QImage, QPixmap
from PyQt6.QtCore import QThread, pyqtSignal, pyqtSlot

from utils.image_utils import TypeCapture, TypePlatform

class DeviceCameraStartup(QThread):
    # Signal to emit the captured image
    change_pixmap_signal = pyqtSignal(QPixmap)
    
    def __init__(self, type_capture: TypeCapture):
        super().__init__()
        
        # Properties Initialization
        self.type_capture = type_capture
        self._run_flag = True
        self._cap = None
    
    @pyqtSlot()
    def stop(self)-> None:
        """Sets run flag to False and waits for thread to finish"""
        self._run_flag = False
        self.wait()
        
    def run(self)-> None:
        """Initialize the camera and start capturing frames"""
        os = platform.system()
        
        if os == TypePlatform.Windows.value:
            self._cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
            
        elif os == TypePlatform.Linux.value:
            self._cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
            
        self._cap.set(cv2.CAP_PROP_FPS, 60)
        
    def general_capture(self)-> None:
        """Capture frames from the camera and emit them as QPixmap"""
        while(self._run_flag):
            ret, cv_img = self._cap.read()
            if (ret):
                pixmap_image = self.convert_cv2_image_to_q_pixmap(cv_img)
                self.change_pixmap_signal.emit(pixmap_image)
                
    def convert_cv2_image_to_q_pixmap(self, MatLike) -> QPixmap:
        """Convert a cv2 image (BGR format) to QPixmap format"""
        rgb_image = cv2.cvtColor(MatLike, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_image.shape
        bytes_per_line = ch * w

        q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap_image = QPixmap.fromImage(q_image)
        return pixmap_image