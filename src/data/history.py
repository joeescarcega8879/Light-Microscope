"""Inspection history: record batches, query/filter, aggregate statistics, export."""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .database import Database, now_str


@dataclass
class Filters:
    date_from: Optional[str] = None   # "YYYY-MM-DD" inclusive
    date_to: Optional[str] = None     # "YYYY-MM-DD" inclusive
    verdict: Optional[str] = None     # "OK" | "NG" | "ERROR"
    reference: Optional[str] = None
    text: Optional[str] = None        # matches file name
    batch_id: Optional[int] = None

    def where(self, ts_col: str = "ts") -> tuple[str, list]:
        clauses, params = [], []
        if self.date_from:
            clauses.append(f"{ts_col} >= ?")
            params.append(f"{self.date_from} 00:00:00")
        if self.date_to:
            clauses.append(f"{ts_col} <= ?")
            params.append(f"{self.date_to} 23:59:59")
        return (" AND ".join(clauses), params)


@dataclass
class Stats:
    total: int = 0
    ok: int = 0
    ng: int = 0
    errors: int = 0
    per_day: list[tuple[str, int, int, int]] = field(default_factory=list)     # (date, ok, ng, err)
    per_reference: list[tuple[str, int, int]] = field(default_factory=list)    # (ref, total, ng)

    @property
    def inspected(self) -> int:
        return self.ok + self.ng

    @property
    def reject_rate(self) -> float:
        """NG / (OK + NG) in percent. Errors are not part of the yield."""
        return (self.ng / self.inspected * 100.0) if self.inspected else 0.0


class HistoryRepository:
    def __init__(self, db: Database):
        self.db = db

    # ── write ──
    def record_batch(self, summary, reference: str, folder: str, user=None,
                     params: Optional[dict] = None) -> int:
        """Persist a finished BatchSummary (duck-typed) in one transaction. Returns the batch id."""
        ts = now_str()
        with self.db.transaction() as conn:
            cur = conn.execute(
                "INSERT INTO batches (started_at, folder, output_dir, reference, user_id, username,"
                " total, ok, ng, errors, cancelled, params_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ts, str(folder), str(summary.output_dir) if summary.output_dir else None, reference,
                 user.id if user else None, user.username if user else None,
                 len(summary.items), summary.ok, summary.ng, summary.errors,
                 1 if summary.cancelled else 0, json.dumps(params) if params else None),
            )
            batch_id = cur.lastrowid
            conn.executemany(
                "INSERT INTO inspections (batch_id, ts, file, path, reference, verdict, defects,"
                " defect_area_pct, reference_index, reasons, error) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                [(batch_id, ts, it.path.name, str(it.path), reference, it.verdict, it.defects,
                  it.defect_area_pct, it.reference_index, it.reasons, it.error) for it in summary.items],
            )
        return batch_id

    def delete_batch(self, batch_id: int):
        self.db.execute("DELETE FROM batches WHERE id = ?", (batch_id,))

    # ── read ──
    def list_batches(self, filters: Optional[Filters] = None, limit: int = 500) -> list:
        f = filters or Filters()
        where, params = f.where("started_at")
        if f.reference:
            where = (where + " AND " if where else "") + "reference = ?"
            params.append(f.reference)
        sql = "SELECT * FROM batches" + (f" WHERE {where}" if where else "") + " ORDER BY id DESC LIMIT ?"
        return self.db.query(sql, params + [limit])

    def get_batch(self, batch_id: int):
        return self.db.query_one("SELECT * FROM batches WHERE id = ?", (batch_id,))

    def batch_items(self, batch_id: int) -> list:
        return self.db.query(
            "SELECT * FROM inspections WHERE batch_id = ? ORDER BY (verdict='OK'), id", (batch_id,))

    def query_inspections(self, filters: Optional[Filters] = None, limit: int = 1000, offset: int = 0) -> list:
        f = filters or Filters()
        where, params = f.where("ts")
        clauses = [where] if where else []
        if f.verdict:
            clauses.append("verdict = ?")
            params.append(f.verdict)
        if f.reference:
            clauses.append("reference = ?")
            params.append(f.reference)
        if f.batch_id is not None:
            clauses.append("batch_id = ?")
            params.append(f.batch_id)
        if f.text:
            clauses.append("file LIKE ? ESCAPE '\\'")
            like = f.text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            params.append(f"%{like}%")
        sql = "SELECT * FROM inspections" + (" WHERE " + " AND ".join(clauses) if clauses else "")
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
        return self.db.query(sql, params + [limit, offset])

    def references_used(self) -> list[str]:
        return [r["reference"] for r in self.db.query("SELECT DISTINCT reference FROM batches ORDER BY reference")]

    def stats(self, filters: Optional[Filters] = None) -> Stats:
        f = filters or Filters()
        where, params = f.where("ts")
        clauses = [where] if where else []
        if f.reference:
            clauses.append("reference = ?")
            params.append(f.reference)
        w = (" WHERE " + " AND ".join(clauses)) if clauses else ""

        t = self.db.query_one(
            "SELECT COUNT(*) total,"
            " COALESCE(SUM(verdict='OK'),0) ok, COALESCE(SUM(verdict='NG'),0) ng,"
            " COALESCE(SUM(verdict='ERROR'),0) err FROM inspections" + w, params)
        s = Stats(total=t["total"], ok=t["ok"], ng=t["ng"], errors=t["err"])
        s.per_day = [(r["d"], r["ok"], r["ng"], r["err"]) for r in self.db.query(
            "SELECT date(ts) d, SUM(verdict='OK') ok, SUM(verdict='NG') ng, SUM(verdict='ERROR') err"
            " FROM inspections" + w + " GROUP BY date(ts) ORDER BY d", params)]
        s.per_reference = [(r["reference"], r["total"], r["ng"]) for r in self.db.query(
            "SELECT reference, COUNT(*) total, SUM(verdict='NG') ng FROM inspections" + w +
            " GROUP BY reference ORDER BY ng DESC, total DESC", params)]
        return s

    def audit_entries(self, limit: int = 500, text: Optional[str] = None) -> list:
        if text:
            like = f"%{text}%"
            return self.db.query(
                "SELECT * FROM audit_log WHERE username LIKE ? OR action LIKE ? OR detail LIKE ?"
                " ORDER BY id DESC LIMIT ?", (like, like, like, limit))
        return self.db.query("SELECT * FROM audit_log ORDER BY id DESC LIMIT ?", (limit,))

    # ── export ──
    @staticmethod
    def export_csv(path, rows: list) -> int:
        cols = ["id", "batch_id", "ts", "file", "reference", "verdict", "defects",
                "defect_area_pct", "reference_index", "reasons", "error"]
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(cols)
            for r in rows:
                w.writerow([_csv_safe(r[c]) for c in cols])
        return len(rows)


def _csv_safe(value):
    """Neutralize spreadsheet formula injection from file names / free text."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value
