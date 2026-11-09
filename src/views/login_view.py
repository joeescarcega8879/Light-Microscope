import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QLineEdit, QWidget


class LoginView(QWidget):
    login_requested = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.initialize_components()

    def initialize_components(self):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "login.ui")
        uic.loadUi(ui_path, self)

        # Confirmation field, only shown while creating the first (administrator) account.
        self.lineEditConfirm = QLineEdit()
        self.lineEditConfirm.setEchoMode(QLineEdit.EchoMode.Password)
        self.lineEditConfirm.setPlaceholderText("Repeat the password")
        self.lineEditConfirm.setMinimumHeight(38)
        idx = self.mainLayout.indexOf(self.lineEditPassword)
        self.mainLayout.insertWidget(idx + 1, self.lineEditConfirm)
        self.lineEditConfirm.hide()
        self._setup_mode = False

        self.btnLogin.clicked.connect(self.login_requested.emit)
        for line in (self.lineEditUsername, self.lineEditPassword, self.lineEditConfirm):
            line.returnPressed.connect(self.login_requested.emit)
        self.chkShowPassword.toggled.connect(self._toggle_password_visibility)

    def _toggle_password_visibility(self, show: bool):
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self.lineEditPassword.setEchoMode(mode)
        self.lineEditConfirm.setEchoMode(mode)

    # ── presenter API ──
    def is_setup_mode(self) -> bool:
        return self._setup_mode

    def set_setup_mode(self, setup: bool):
        self._setup_mode = setup
        self.lineEditConfirm.setVisible(setup)
        self.lblSubtitle.setText("First run: create the administrator account" if setup else "Sign in to continue")
        self.btnLogin.setText("Create account" if setup else "Sign In")

    def username(self) -> str:
        return self.lineEditUsername.text().strip()

    def password(self) -> str:
        return self.lineEditPassword.text()

    def confirm(self) -> str:
        return self.lineEditConfirm.text()

    def show_error(self, message: str):
        self.lblError.setText(message)
        self.lblError.setVisible(bool(message))

    def clear_sensitive(self):
        self.lineEditPassword.clear()
        self.lineEditConfirm.clear()
