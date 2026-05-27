
class LoginPresenter:
    def __init__(self, view, on_login_success):
        self.view = view
        self.on_login_success = on_login_success
        self._connect_signals()
        
    def _connect_signals(self):
        self.view.login_requested.connect(self._handle_login)
        
    
    def _handle_login(self):
        self.on_login_success()