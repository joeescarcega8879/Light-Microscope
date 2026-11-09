import os
from PyQt6 import uic
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QDialog, QPushButton


class SettingsView(QDialog):
    theme_selected = pyqtSignal(str)
    manage_users_requested = pyqtSignal()

    def __init__(self, theme_names: list[str], current_theme: str | None = None, can_manage_users: bool = False):
        super().__init__()
        self._selected_theme = current_theme or ""
        self._initialize_components(theme_names)
        if can_manage_users:
            btn = QPushButton("Manage users…")
            btn.clicked.connect(self.manage_users_requested.emit)
            self.rootLayout.insertWidget(self.rootLayout.count() - 1, btn)

    def _initialize_components(self, theme_names: list[str]):
        ui_path = os.path.join(os.path.dirname(__file__), "ui", "settings_dialog.ui")
        uic.loadUi(ui_path, self)

        self.cmbTheme.addItems(theme_names)
        if self._selected_theme in theme_names:
            self.cmbTheme.setCurrentText(self._selected_theme)

        self.cmbTheme.currentTextChanged.connect(self._on_theme_changed)
        self.btnApply.clicked.connect(self._on_apply)
        self.btnCancel.clicked.connect(self.reject)

    def _on_theme_changed(self, theme_name: str):
        self._selected_theme = theme_name

    def _on_apply(self):
        if self._selected_theme:
            self.theme_selected.emit(self._selected_theme)
            self.accept()
