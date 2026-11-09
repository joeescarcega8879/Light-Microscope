"""SQLite storage for users, inspection history and the audit log."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional

from ..utils.logging_config import APP_DIR

DEFAULT_DB_PATH = APP_DIR / "light_microscope.db"

# Each entry migrates the schema from version i to i+1.
_MIGRATIONS = [
    """
    CREATE TABLE users (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        username       TEXT NOT NULL UNIQUE COLLATE NOCASE,
        password_hash  TEXT NOT NULL,
        role           TEXT NOT NULL CHECK (role IN ('operator','supervisor','admin')),
        active         INTEGER NOT NULL DEFAULT 1,
        created_at     TEXT NOT NULL,
        last_login     TEXT,
        failed_attempts INTEGER NOT NULL DEFAULT 0,
        locked_until   TEXT
    );
    CREATE TABLE batches (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        started_at  TEXT NOT NULL,
        folder      TEXT NOT NULL,
        output_dir  TEXT,
        reference   TEXT NOT NULL,
        user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
        username    TEXT,
        total       INTEGER NOT NULL,
        ok          INTEGER NOT NULL,
        ng          INTEGER NOT NULL,
        errors      INTEGER NOT NULL,
        cancelled   INTEGER NOT NULL DEFAULT 0,
        params_json TEXT
    );
    CREATE TABLE inspections (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id         INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
        ts               TEXT NOT NULL,
        file             TEXT NOT NULL,
        path             TEXT NOT NULL,
        reference        TEXT NOT NULL,
        verdict          TEXT NOT NULL CHECK (verdict IN ('OK','NG','ERROR')),
        defects          INTEGER NOT NULL DEFAULT 0,
        defect_area_pct  REAL NOT NULL DEFAULT 0,
        reference_index  INTEGER NOT NULL DEFAULT 0,
        reasons          TEXT NOT NULL DEFAULT '',
        error            TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX idx_inspections_ts ON inspections(ts);
    CREATE INDEX idx_inspections_verdict ON inspections(verdict);
    CREATE INDEX idx_inspections_batch ON inspections(batch_id);
    CREATE TABLE audit_log (
        id        INTEGER PRIMARY KEY AUTOINCREMENT,
        ts        TEXT NOT NULL,
        user_id   INTEGER,
        username  TEXT NOT NULL,
        action    TEXT NOT NULL,
        detail    TEXT NOT NULL DEFAULT ''
    );
    CREATE INDEX idx_audit_ts ON audit_log(ts);
    """,
]


def now_str() -> str:
    """Local time, second precision. Stored as text so SQLite date() groups by local day."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class Database:
    def __init__(self, path: Optional[Path | str] = None):
        self.path = str(path) if path is not None else str(DEFAULT_DB_PATH)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self):
        version = self.conn.execute("PRAGMA user_version").fetchone()[0]
        for i in range(version, len(_MIGRATIONS)):
            # executescript commits implicitly, so apply the script, then bump the version.
            self.conn.executescript(_MIGRATIONS[i])
            self.conn.execute(f"PRAGMA user_version = {i + 1}")
            self.conn.commit()

    @property
    def schema_version(self) -> int:
        return self.conn.execute("PRAGMA user_version").fetchone()[0]

    @contextmanager
    def transaction(self):
        try:
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

    def query(self, sql: str, params: Iterable = ()) -> list[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchall()

    def query_one(self, sql: str, params: Iterable = ()) -> Optional[sqlite3.Row]:
        return self.conn.execute(sql, tuple(params)).fetchone()

    def execute(self, sql: str, params: Iterable = ()) -> sqlite3.Cursor:
        with self.transaction():
            return self.conn.execute(sql, tuple(params))

    def log_audit(self, username: str, action: str, detail: str = "", user_id: Optional[int] = None):
        self.execute(
            "INSERT INTO audit_log (ts, user_id, username, action, detail) VALUES (?,?,?,?,?)",
            (now_str(), user_id, username, action, detail),
        )

    def close(self):
        self.conn.close()
