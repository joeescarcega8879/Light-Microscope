import logging

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from ..data.auth import ROLES, AuthError, AuthService
from ..data.session import Session

log = logging.getLogger(__name__)


class UserManagementPresenter(QObject):
    def __init__(self, view, auth: AuthService, session: Session):
        super().__init__()
        self.view, self.auth, self.session = view, auth, session
        view.add_requested.connect(self._add)
        view.role_requested.connect(self._change_role)
        view.password_requested.connect(self._reset_password)
        view.toggle_active_requested.connect(self._toggle_active)
        self.refresh()

    def refresh(self):
        users = self.auth.list_users()
        self.view.set_users(users, {u.id: self.auth.last_login(u.id) for u in users})

    def _guard(self, fn):
        if not self.session.can("manage_users"):
            return
        try:
            fn()
        except AuthError as exc:
            QMessageBox.warning(self.view, "Users", str(exc))
        self.refresh()

    def _ask_password(self, title: str):
        pw, ok = QInputDialog.getText(self.view, title, "Password (min 8 characters):", QLineEdit.EchoMode.Password)
        return pw if ok else None

    def _add(self):
        def run():
            name, ok = QInputDialog.getText(self.view, "Add user", "Username:")
            if not ok:
                return
            role, ok = QInputDialog.getItem(self.view, "Add user", "Role:", list(ROLES), 0, False)
            if not ok:
                return
            pw = self._ask_password("Add user")
            if pw is None:
                return
            user = self.auth.create_user(name, pw, role)
            self.session.audit("user_created", f"{user.username} ({user.role})")
        self._guard(run)

    def _change_role(self, user_id: int):
        def run():
            user = self.auth.get_user(user_id)
            if user.id == self.session.user.id:
                raise AuthError("You cannot change your own role.")
            role, ok = QInputDialog.getItem(self.view, "Change role", f"Role for {user.username}:",
                                            list(ROLES), ROLES.index(user.role), False)
            if ok and role != user.role:
                self.auth.set_role(user_id, role)
                self.session.audit("role_changed", f"{user.username}: {user.role} -> {role}")
        self._guard(run)

    def _reset_password(self, user_id: int):
        def run():
            user = self.auth.get_user(user_id)
            pw = self._ask_password(f"New password for {user.username}")
            if pw is not None:
                self.auth.set_password(user_id, pw)
                self.session.audit("password_reset", user.username)
        self._guard(run)

    def _toggle_active(self, user_id: int):
        def run():
            user = self.auth.get_user(user_id)
            if user.id == self.session.user.id:
                raise AuthError("You cannot disable your own account.")
            self.auth.set_active(user_id, not user.active)
            self.session.audit("user_enabled" if not user.active else "user_disabled", user.username)
        self._guard(run)
