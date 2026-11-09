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
from src.views.length_measurement_view import LengthMeasurementView
from src.views.contour_detection_view import ContourDetectionView
from src.views.part_inspection_view import PartInspectionView
from src.views.history_view import HistoryView
from src.views.user_management_view import UserManagementView

from src.presenters.login_presenter import LoginPresenter
from src.presenters.main_presenter import MainPresenter
from src.presenters.device_camera_presenter import DeviceCameraPresenter
from src.presenters.image_comparison_presenter import ImageComparisonPresenter
from src.presenters.settings_presenter import SettingsPresenter
from src.presenters.yolo_studio_presenter import YoloStudioPresenter
from src.presenters.length_measurement_presenter import LengthMeasurementPresenter
from src.presenters.contour_detection_presenter import ContourDetectionPresenter
from src.presenters.part_inspection_presenter import PartInspectionPresenter
from src.presenters.history_presenter import HistoryPresenter
from src.presenters.user_management_presenter import UserManagementPresenter

from src.data.database import Database
from src.data.auth import AuthService
from src.data.history import HistoryRepository
from src.data.session import Session

from src.utils.theme_manager import ThemeManager
from src.utils import app_settings
from src.utils.logging_config import setup_logging


class MainApplication:
    def __init__(self):
        css_dir = os.path.join(os.path.dirname(__file__), "src", "assets", "css")
        self._theme_manager = ThemeManager(css_dir)
        if not self._theme_manager.apply_theme(app_settings.get_theme()):
            self._theme_manager.apply_theme("light")
        self.db = Database()
        self.auth = AuthService(self.db)
        self.history = HistoryRepository(self.db)
        self.session = Session(self.db)
        self.open_login_view()

    def open_login_view(self):
        self.login_view = LoginView()
        self.login_presenter = LoginPresenter(
            self.login_view, self.auth, on_login_success=self._initialize_main_window
        )
        self.login_view.show()

    def _initialize_main_window(self, user):
        self.session = Session(self.db, user)
        self.session.audit("login")
        self.main_window = MainView()
        self.main_presenter = MainPresenter(self.main_window, self)
        self.main_window.apply_permissions(self.session)
        self.main_window.show()
        self.login_view.close()

    def sign_out(self):
        self.session.audit("logout")
        old_main = self.main_window
        self.session = Session(self.db)
        # Open the login window FIRST so the app never has zero visible windows
        # (Qt quits when the last window closes).
        self.open_login_view()
        for name in ("device_camera_view", "image_comparison_view", "comparison_result_view",
                     "ai_studio_view", "length_measurement_view", "contour_detection_view",
                     "part_inspection_view", "history_view"):
            view = getattr(self, name, None)
            if view is not None and view.isVisible():
                view.close()
        old_main.close()

    def _show_dashboard(self):
        if self.session.user is not None:
            self.main_window.show()

    def open_camera_view(self):
        self.device_camera_view = DeviceCameraView()
        self.device_camera_presenter = DeviceCameraPresenter(self.device_camera_view)
        self.device_camera_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.device_camera_view.setWindowTitle("Video Capture")
        self.device_camera_view.show()

    def open_image_comparison_view(self):
        self.image_comparison_view = ImageComparisonView()
        self.image_comparison_presenter = ImageComparisonPresenter(self.image_comparison_view, self)
        self.image_comparison_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.image_comparison_view.setWindowTitle("Image Comparison")
        self.image_comparison_view.show()

    def open_comparison_result_view(self, diff, heatmap, contour_img, stats_text: str):
        self.comparison_result_view = ImageComparisonResultView()
        self.comparison_result_view.display_diff(diff)
        self.comparison_result_view.display_heatmap(heatmap)
        self.comparison_result_view.display_contours(contour_img)
        self.comparison_result_view.set_stats(stats_text)
        self.comparison_result_view.setWindowTitle("Comparison Results")
        self.comparison_result_view.show()

    def open_ai_studio_view(self):
        self.ai_studio_view = YoloStudioView()
        self.ai_studio_presenter = YoloStudioPresenter(self.ai_studio_view)
        self.ai_studio_view.view_closed.connect(self._show_dashboard)
        self.main_window.hide()
        self.ai_studio_view.setWindowTitle("AI Studio — Annotate & Train")
        self.ai_studio_view.show()

    def open_length_measurement_view(self):
        self.length_measurement_view = LengthMeasurementView()
        self.length_measurement_presenter = LengthMeasurementPresenter(self.length_measurement_view)
        self.length_measurement_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.length_measurement_view.setWindowTitle("Length Measurement")
        self.length_measurement_view.show()

    def open_contour_detection_view(self):
        self.contour_detection_view = ContourDetectionView()
        self.contour_detection_presenter = ContourDetectionPresenter(self.contour_detection_view)
        self.contour_detection_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.contour_detection_view.setWindowTitle("Contour Detection")
        self.contour_detection_view.show()

    def open_part_inspection_view(self):
        self.part_inspection_view = PartInspectionView()
        self.part_inspection_presenter = PartInspectionPresenter(
            self.part_inspection_view, session=self.session, history=self.history)
        self.part_inspection_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.part_inspection_view.show()

    def open_history_view(self):
        self.history_view = HistoryView()
        self.history_presenter = HistoryPresenter(self.history_view, self.history, self.session)
        self.history_view.view_closed.connect(self._show_dashboard)

        self.main_window.hide()
        self.history_view.show()

    def open_user_management(self, parent=None):
        dialog = UserManagementView(parent)
        presenter = UserManagementPresenter(dialog, self.auth, self.session)  # noqa: F841 (kept alive by signals)
        dialog.exec()

    def open_settings_dialog(self):
        theme_names = self._theme_manager.theme_names()
        current = self._theme_manager.current_theme()
        dialog = SettingsView(theme_names, current, can_manage_users=self.session.can("manage_users"))
        dialog.manage_users_requested.connect(lambda: self.open_user_management(dialog))
        presenter = SettingsPresenter(dialog, self._theme_manager)
        dialog.exec()


if __name__ == "__main__":
    setup_logging()
    app = QApplication(sys.argv)
    app.setOrganizationName(app_settings.ORGANIZATION)
    app.setApplicationName(app_settings.APPLICATION)
    main_application = MainApplication()
    app.exec()
