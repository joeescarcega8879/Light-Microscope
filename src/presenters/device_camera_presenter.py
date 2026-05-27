import sys
from typing import Optional
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QLineEdit
from PyQt6.QtCore import pyqtSlot, QObject
from PyQt6.QtGui import QPixmap

from models.device_camera_startup import DeviceCameraStartup

class DeviceCameraPresenter(QObject):
    """Presenter class for handling camera operations and updating the view with captured images."""
    def __init__(self, view):
        super().__init__()
        self.view = view
        self.video_capture_instance: Optional[DeviceCameraStartup] = None
        
        self._connect_signals()
        
    def _connect_signals(self):
        self.view.video_capture_requested.connect(self._start_video_capture)
        
    
    def _start_video_capture(self, type_capture):
        """Starts the video capture process based on the specified type."""
        self.video_capture_instance = DeviceCameraStartup(type_capture)
        self.video_capture_instance.change_pixmap_signal.connect(self.update_image)
        self.video_capture_instance.start()
        self.video_capture_instance.general_capture()
    
    @pyqtSlot(QPixmap)
    def update_image(self, pixmap: QPixmap):
        """Updates the view with the captured image."""
        self.view.setPixmap(pixmap)
    
    def stop_video_capture(self):
        """Stops the video capture process and releases resources."""
        if self.video_capture_instance is not None:
            self.video_capture_instance.stop()