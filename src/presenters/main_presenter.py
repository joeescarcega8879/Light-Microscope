
class MainPresenter:
    def __init__(self, view, main_app):
        self.view = view
        self.main_app = main_app
        
        self._connect_signals()
        
        
    def _connect_signals(self):
        self.view.video_capture_requested.connect(self.main_app.open_camera_view)
        self.view.settings_requested.connect(self.main_app.open_settings_dialog)