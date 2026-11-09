"""Users, roles and password handling (stdlib only: PBKDF2-SHA256)."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from .database import Database, now_str

PBKDF2_ITERATIONS = 240_000
MIN_PASSWORD_LENGTH = 8
MAX_FAILED_ATTEMPTS = 5
LOCK_SECONDS = 60

ROLES = ("operator", "supervisor", "admin")
_RANK = {r: i for i, r in enumerate(ROLES)}

# permission -> minimum role
PERMISSIONS = {
    "run_inspection": "operator",
    "view_history": "operator",
    "use_camera": "operator",
    "export_reports": "supervisor",
    "edit_references": "supervisor",
    "use_ai_studio": "supervisor",
    "view_audit": "supervisor",
    "manage_users": "admin",
    "delete_history": "admin",
}

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
_DUMMY_HASH = None


class AuthError(Exception):
    """A user-facing validation/authentication problem."""


@dataclass(frozen=True)
class User:
    id: int
    username: str
    role: str
    active: bool = True

    def can(self, permission: str) -> bool:
        need = PERMISSIONS.get(permission)
        return need is not None and _RANK[self.role] >= _RANK[need]


def hash_password(password: str, iterations: Optional[int] = None) -> str:
    iterations = iterations or PBKDF2_ITERATIONS
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iters, salt_hex, hash_hex = stored.split("$")
        if scheme != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), int(iters))
        return hmac.compare_digest(digest, bytes.fromhex(hash_hex))
    except (ValueError, TypeError):
        return False


def validate_password(password: str):
    if len(password) < MIN_PASSWORD_LENGTH:
        raise AuthError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")


def validate_username(username: str):
    if not _USERNAME_RE.match(username):
        raise AuthError("Username must be 3-32 characters: letters, digits, '.', '_' or '-'.")


class AuthService:
    def __init__(self, db: Database):
        self.db = db

    @staticmethod
    def _to_user(row) -> User:
        return User(row["id"], row["username"], row["role"], bool(row["active"]))

    # ── queries ──
    def has_users(self) -> bool:
        return self.db.query_one("SELECT 1 FROM users LIMIT 1") is not None

    def list_users(self) -> list[User]:
        return [self._to_user(r) for r in self.db.query("SELECT * FROM users ORDER BY username COLLATE NOCASE")]

    def get_user(self, user_id: int) -> Optional[User]:
        row = self.db.query_one("SELECT * FROM users WHERE id = ?", (user_id,))
        return self._to_user(row) if row else None

    def last_login(self, user_id: int) -> str:
        row = self.db.query_one("SELECT last_login FROM users WHERE id = ?", (user_id,))
        return (row["last_login"] or "") if row else ""

    # ── mutations ──
    def create_user(self, username: str, password: str, role: str = "operator") -> User:
        username = username.strip()
        validate_username(username)
        validate_password(password)
        if role not in ROLES:
            raise AuthError(f"Unknown role '{role}'.")
        if self.db.query_one("SELECT 1 FROM users WHERE username = ?", (username,)):
            raise AuthError(f"User '{username}' already exists.")
        cur = self.db.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?,?,?,?)",
            (username, hash_password(password), role, now_str()),
        )
        return User(cur.lastrowid, username, role, True)

    def _active_admins(self, excluding: Optional[int] = None) -> int:
        row = self.db.query_one(
            "SELECT COUNT(*) c FROM users WHERE role='admin' AND active=1 AND id != ?", (excluding or -1,))
        return row["c"]

    def set_role(self, user_id: int, role: str):
        if role not in ROLES:
            raise AuthError(f"Unknown role '{role}'.")
        user = self.get_user(user_id)
        if user is None:
            raise AuthError("User not found.")
        if user.role == "admin" and role != "admin" and self._active_admins(excluding=user_id) == 0:
            raise AuthError("You cannot demote the last active administrator.")
        self.db.execute("UPDATE users SET role = ? WHERE id = ?", (role, user_id))

    def set_active(self, user_id: int, active: bool):
        user = self.get_user(user_id)
        if user is None:
            raise AuthError("User not found.")
        if not active and user.role == "admin" and self._active_admins(excluding=user_id) == 0:
            raise AuthError("You cannot deactivate the last active administrator.")
        self.db.execute("UPDATE users SET active = ? WHERE id = ?", (1 if active else 0, user_id))

    def set_password(self, user_id: int, new_password: str):
        validate_password(new_password)
        self.db.execute(
            "UPDATE users SET password_hash = ?, failed_attempts = 0, locked_until = NULL WHERE id = ?",
            (hash_password(new_password), user_id),
        )

    # ── authentication ──
    def authenticate(self, username: str, password: str) -> User:
        """Return the user, or raise AuthError. Same message for unknown user / wrong password."""
        global _DUMMY_HASH
        row = self.db.query_one("SELECT * FROM users WHERE username = ?", (username.strip(),))
        generic = AuthError("Invalid username or password.")

        if row is None:
            if _DUMMY_HASH is None:
                _DUMMY_HASH = hash_password("dummy-password")
            verify_password(password, _DUMMY_HASH)   # keep timing similar
            raise generic

        locked_until = row["locked_until"]
        if locked_until and datetime.strptime(locked_until, "%Y-%m-%d %H:%M:%S") > datetime.now():
            raise AuthError("Too many failed attempts. Try again in a minute.")

        if not verify_password(password, row["password_hash"]):
            attempts = row["failed_attempts"] + 1
            if attempts >= MAX_FAILED_ATTEMPTS:
                until = (datetime.now() + timedelta(seconds=LOCK_SECONDS)).strftime("%Y-%m-%d %H:%M:%S")
                self.db.execute("UPDATE users SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                                (until, row["id"]))
                self.db.log_audit(row["username"], "login_locked", f"{MAX_FAILED_ATTEMPTS} failed attempts",
                                  row["id"])
            else:
                self.db.execute("UPDATE users SET failed_attempts = ? WHERE id = ?", (attempts, row["id"]))
            raise generic

        if not row["active"]:
            raise AuthError("This account is disabled. Contact an administrator.")

        self.db.execute(
            "UPDATE users SET failed_attempts = 0, locked_until = NULL, last_login = ? WHERE id = ?",
            (now_str(), row["id"]),
        )
        return self._to_user(row)
