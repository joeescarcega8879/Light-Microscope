
class MainPresenter:
    # Constructor
    def __init__(self, view, main_app):
        self.view = view
        self.main_app = main_app
        
        self._connect_signals()
    
    # Private methods    
    def _connect_signals(self):
        self.view.video_capture_requested.connect(self.main_app.open_camera_view)
        self.view.settings_requested.connect(self.main_app.open_settings_dialog)
        self.view.image_comparison_requested.connect(self.main_app.open_image_comparison_view)
        self.view.ai_studio_requested.connect(self.main_app.open_ai_studio_view)
        self.view.measurement_requested.connect(self.main_app.open_length_measurement_view)
        self.view.contour_detection_requested.connect(self.main_app.open_contour_detection_view)