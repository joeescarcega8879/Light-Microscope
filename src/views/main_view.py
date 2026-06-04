import os
from PyQt6 import uic, QtCore
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QMainWindow


class MainView(QMainWindow):
    video_capture_requested = pyqtSignal()
    image_comparison_requested = pyqtSignal()
    measurement_requested = pyqtSignal()
    settings_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.initialize_components()

    def initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "main_window.ui")
        uic.loadUi(ui_path, self)

        self.btnVideo.clicked.connect(self.video_capture_requested.emit)
        self.btnImages.clicked.connect(self.image_comparison_requested.emit)
        self.btnMeasure.clicked.connect(self.measurement_requested.emit)
        self.btnSettings.clicked.connect(self.settings_requested.emit)
        
    def open_child_form(self, objectInstance, mdiSubWindow):
        """"
        Opens a child form inside the MDI container.
        Closes any previously opened child forms.
        
        :param objectInstance: The instance of the child form to be opened.
        :param mdiSubWindow: The QMdiSubWindow that will contain the child form.

        """
        
        self.mdiArea.closeAllSubWindows()
        
        mdiSubWindow.setWidget(objectInstance)
        mdiSubWindow.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
        mdiSubWindow.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)
        
        self.mdiArea.addSubWindow(mdiSubWindow)
        mdiSubWindow.showMaximized()
        
