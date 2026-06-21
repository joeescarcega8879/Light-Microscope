import os
import sys
from PyQt6.QtWidgets import QApplication

from src.views.main_view import MainView
from src.views.login_view import LoginView
from src.views.device_camera_view import DeviceCameraView
from src.views.settings_view import SettingsView
from src.views.image_comparison_view import ImageComparisonView
from src.views.image_comparison_result_view import ImageComparisonResultView
from src.views.yolo_studio_view import YoloStudioView

from src.presenters.login_presenter import LoginPresenter
from src.presenters.main_presenter import MainPresenter
from src.presenters.device_camera_presenter import DeviceCameraPresenter
from src.presenters.image_comparison_presenter import ImageComparisonPresenter
from src.presenters.settings_presenter import SettingsPresenter
from src.presenters.yolo_studio_presenter import YoloStudioPresenter

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

    def _show_dashboard(self):
        self.main_window.showMaximized()

    def open_camera_view(self):
        self.device_camera_view = DeviceCameraView()
        self.device_camera_presenter = DeviceCameraPresenter(self.device_camera_view)
        self.device_camera_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.device_camera_view.setWindowTitle("Video Capture")
        self.device_camera_view.showMaximized()

    def open_image_comparison_view(self):
        self.image_comparison_view = ImageComparisonView()
        self.image_comparison_presenter = ImageComparisonPresenter(self.image_comparison_view, self)
        self.image_comparison_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.image_comparison_view.setWindowTitle("Image Comparison")
        self.image_comparison_view.showMaximized()

    def open_comparison_result_view(self, diff, heatmap, contour_img, stats_text: str):
        self.comparison_result_view = ImageComparisonResultView()
        self.comparison_result_view.display_diff(diff)
        self.comparison_result_view.display_heatmap(heatmap)
        self.comparison_result_view.display_contours(contour_img)
        self.comparison_result_view.set_stats(stats_text)
        self.comparison_result_view.setWindowTitle("Comparison Results")
        self.comparison_result_view.showMaximized()

    def open_ai_studio_view(self):
        self.ai_studio_view = YoloStudioView()
        self.ai_studio_presenter = YoloStudioPresenter(self.ai_studio_view)
        self.ai_studio_view.view_closed.connect(self._show_dashboard)
        self.main_window.hide()
        self.ai_studio_view.setWindowTitle("AI Studio — Annotate & Train")
        self.ai_studio_view.showMaximized()

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
