import os
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtWidgets import QMdiSubWindow

from src.views.main_view import MainView
from src.views.login_view import LoginView
from src.views.device_camera_view import DeviceCameraView
from src.views.settings_view import SettingsView

from src.presenters.login_presenter import LoginPresenter
from src.presenters.main_presenter import MainPresenter
from src.presenters.device_camera_presenter import DeviceCameraPresenter
from src.presenters.settings_presenter import SettingsPresenter

from src.utils.theme_manager import ThemeManager


class MainApplication:
    def __init__(self):
        css_dir = os.path.join(os.path.dirname(__file__), "src", "assets", "css")
        self._theme_manager = ThemeManager(css_dir)
        self._theme_manager.apply_theme("light")
        self.open_login_view()

    def open_login_view(self):
        self.login_view = LoginView()
        self.login_presenter = LoginPresenter(
            self.login_view, on_login_success=self._initialize_main_window
        )
        self.login_view.show()

    def _initialize_main_window(self):
        self.main_window = MainView()
        self.main_presenter = MainPresenter(self.main_window, self)

        self.main_window.show()
        self.login_view.close()

    def open_camera_view(self):

        self.device_camera_view = DeviceCameraView()
        self.device_camera_presenter = DeviceCameraPresenter(self.device_camera_view)
        
        mdi_subwindow = QMdiSubWindow()
        
        self.main_window.open_child_form(self.device_camera_view, mdi_subwindow)

    def open_settings_dialog(self):
        theme_names = self._theme_manager.theme_names()
        current = self._theme_manager.current_theme()

        dialog = SettingsView(theme_names, current)
        presenter = SettingsPresenter(dialog, self._theme_manager)
        dialog.exec()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main_application = MainApplication()
    app.exec()
