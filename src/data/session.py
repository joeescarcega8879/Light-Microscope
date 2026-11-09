from typing import Optional

from .auth import User
from .database import Database


class Session:
    """The signed-in user plus helpers for permission checks and auditing."""

    def __init__(self, db: Database, user: Optional[User] = None):
        self.db = db
        self.user = user

    @property
    def username(self) -> str:
        return self.user.username if self.user else "(none)"

    @property
    def role(self) -> str:
        return self.user.role if self.user else ""

    def can(self, permission: str) -> bool:
        return bool(self.user and self.user.can(permission))

    def audit(self, action: str, detail: str = ""):
        self.db.log_audit(self.username, action, detail, self.user.id if self.user else None)
