import logging

from ..data.auth import AuthError, AuthService

log = logging.getLogger(__name__)


class LoginPresenter:
    def __init__(self, view, auth: AuthService, on_login_success):
        self.view = view
        self.auth = auth
        self.on_login_success = on_login_success   # callable(User)
        self.view.set_setup_mode(not auth.has_users())
        self.view.login_requested.connect(self._handle_login)

    def _handle_login(self):
        self.view.show_error("")
        try:
            if self.view.is_setup_mode():
                user = self._create_first_admin()
            else:
                user = self.auth.authenticate(self.view.username(), self.view.password())
        except AuthError as exc:
            self.view.show_error(str(exc))
            self.view.clear_sensitive()
            return
        self.view.clear_sensitive()
        self.on_login_success(user)

    def _create_first_admin(self):
        if self.view.password() != self.view.confirm():
            raise AuthError("The passwords do not match.")
        if self.auth.has_users():       # someone else created it meanwhile
            raise AuthError("An account already exists. Please sign in.")
        user = self.auth.create_user(self.view.username(), self.view.password(), "admin")
        self.auth.db.log_audit(user.username, "admin_created", "first-run setup", user.id)
        return self.auth.authenticate(self.view.username(), self.view.password())
