import sys
from PyQt6.QtWidgets import QApplication

from src.views.main_window import MainWindow
from src.views.login_view import LoginView

from src.presenters.login_presenter import LoginPresenter


class MainApplication:
    # Constructor
    def __init__(self):
        self.open_login_view()
    
    def open_login_view(self):
        self.login_view = LoginView()
        self.login_presenter = LoginPresenter(self.login_view, on_login_success=self.open_main_window)
        self.login_view.show()
    
    
    def open_main_window(self):
        self.main_window = MainWindow()
        self.main_window.show()
        self.login_view.close()

if __name__ == "__main__":
    
    app = QApplication(sys.argv)
    
    main_application = MainApplication()
    
    app.exec()