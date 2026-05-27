import os
import sys
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QWidget, QPushButton ,QApplication

class DeviceCameraView(QWidget):
    video_capture_requested = pyqtSignal()
    
    # Constructor
    def __init__(self):
        super().__init__()
        
        self.initialize_components()
        
    def initialize_components(self):
        # Load ui Path
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "camera_view_widget.ui")
        
        # Load the UI file
        uic.loadUi(ui_path, self)
        
        # Connect signals to slots
        # self.btnVideo.clicked.connect(self.video_capture_requested.emit)
        