"""SQLite persistence for runs and their event logs."""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Iterable

from .config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    meta_json TEXT NOT NULL,
    report_json TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    run_id TEXT NOT NULL,
    seq INTEGER NOT NULL,
    type TEXT NOT NULL,
    data_json TEXT NOT NULL,
    ts REAL NOT NULL,
    PRIMARY KEY (run_id, seq)
);
"""

_conn: sqlite3.Connection | None = None


def _db() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        settings.db_path.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(settings.db_path, check_same_thread=False)
        _conn.executescript(_SCHEMA)
        _conn.commit()
    return _conn


def create_run(ctx: Any) -> None:
    meta = ctx.to_meta_dict() if hasattr(ctx, "to_meta_dict") else {"run_id": ctx.run_id}
    db = _db()
    db.execute(
        "INSERT OR REPLACE INTO runs (run_id, meta_json, report_json, created_at) VALUES (?, ?, NULL, ?)",
        (meta["run_id"], json.dumps(meta), time.time()),
    )
    db.commit()


def save_report(report) -> None:
    db = _db()
    db.execute(
        "UPDATE runs SET meta_json = ?, report_json = ? WHERE run_id = ?",
        (report.meta.model_dump_json(), report.model_dump_json(), report.meta.run_id),
    )
    db.commit()


def mark_failed(run_id: str, message: str) -> None:
    db = _db()
    row = db.execute("SELECT meta_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return
    meta = json.loads(row[0])
    meta["status"] = "failed"
    meta["error"] = message[:500]
    db.execute("UPDATE runs SET meta_json = ? WHERE run_id = ?", (json.dumps(meta), run_id))
    db.commit()


def get_run_meta(run_id: str) -> dict | None:
    row = _db().execute("SELECT meta_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return json.loads(row[0]) if row else None


def get_report_json(run_id: str) -> str | None:
    row = _db().execute("SELECT report_json FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    return row[0] if row and row[0] else None


def recent_runs(limit: int = 20) -> list[dict]:
    rows = _db().execute(
        "SELECT meta_json FROM runs ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [json.loads(r[0]) for r in rows]


def append_event(run_id: str, type_: str, data: dict) -> int:
    db = _db()
    row = db.execute("SELECT COALESCE(MAX(seq), 0) FROM events WHERE run_id = ?", (run_id,)).fetchone()
    seq = (row[0] or 0) + 1
    db.execute(
        "INSERT INTO events (run_id, seq, type, data_json, ts) VALUES (?, ?, ?, ?, ?)",
        (run_id, seq, type_, json.dumps(data), time.time()),
    )
    db.commit()
    return seq


def events_after(run_id: str, after: int = 0) -> Iterable[dict]:
    rows = _db().execute(
        "SELECT seq, type, data_json, ts FROM events WHERE run_id = ? AND seq > ? ORDER BY seq",
        (run_id, after),
    ).fetchall()
    for seq, type_, data_json, ts in rows:
        yield {"seq": seq, "type": type_, "data": json.loads(data_json), "ts": ts}
