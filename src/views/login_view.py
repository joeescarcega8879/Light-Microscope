import os
import sys
from PyQt6 import uic
from PyQt6.QtWidgets import QWidget, QApplication

from PyQt6.QtCore import pyqtSignal

class LoginView(QWidget):
    login_requested = pyqtSignal()
    
    # Constructor
    def __init__(self):
        super().__init__()
        
        self.initialize_components()
        
    def initialize_components(self):
        # Load ui Path
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "login.ui")
        
        # Load the UI file
        uic.loadUi(ui_path, self)
        
        # Request signals
        self.btnLogin.clicked.connect(self.login_requested.emit)
