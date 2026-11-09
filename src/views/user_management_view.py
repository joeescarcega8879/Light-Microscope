from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)


class UserManagementView(QDialog):
    add_requested = pyqtSignal()
    role_requested = pyqtSignal(int)
    password_requested = pyqtSignal(int)
    toggle_active_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage users")
        self.resize(640, 380)
        lay = QVBoxLayout(self)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["User", "Role", "Status", "Last sign-in"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.btnAdd = QPushButton("Add user…")
        self.btnRole = QPushButton("Change role…")
        self.btnPassword = QPushButton("Reset password…")
        self.btnToggle = QPushButton("Enable / disable")
        for b in (self.btnAdd, self.btnRole, self.btnPassword, self.btnToggle):
            row.addWidget(b)
        row.addStretch(1)
        lay.addLayout(row)
        self.lblInfo = QLabel("Roles: operator = run inspections · supervisor = + references, reports, AI Studio · admin = + users")
        self.lblInfo.setWordWrap(True)
        lay.addWidget(self.lblInfo)

        self.btnAdd.clicked.connect(self.add_requested.emit)
        self.btnRole.clicked.connect(lambda: self._emit(self.role_requested))
        self.btnPassword.clicked.connect(lambda: self._emit(self.password_requested))
        self.btnToggle.clicked.connect(lambda: self._emit(self.toggle_active_requested))

    def set_users(self, users: list, last_logins: dict[int, str]):
        self.table.setRowCount(len(users))
        for r, u in enumerate(users):
            cells = [u.username, u.role, "active" if u.active else "disabled", last_logins.get(u.id, "") or "never"]
            for c, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if c == 0:
                    item.setData(Qt.ItemDataRole.UserRole, u.id)
                self.table.setItem(r, c, item)

    def selected_user_id(self) -> Optional[int]:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        return int(self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole))

    def _emit(self, signal):
        uid = self.selected_user_id()
        if uid is not None:
            signal.emit(uid)
