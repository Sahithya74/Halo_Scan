"""SQLite storage for users, patients, sessions, the audit log and analyses.

Schema is created with CREATE TABLE IF NOT EXISTS plus additive ALTER TABLE migrations, so
an existing analysis_history.db from earlier versions keeps working.
"""
from __future__ import annotations

import datetime as _dt
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_code TEXT NOT NULL UNIQUE,
    mrn_index TEXT NOT NULL UNIQUE,
    mrn_enc TEXT NOT NULL,
    name_enc TEXT NOT NULL,
    dob_enc TEXT,
    sex TEXT,
    created_by INTEGER,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'doctor', 'nurse', 'patient')),
    display_name_enc TEXT,
    patient_id INTEGER REFERENCES patients(id),
    active INTEGER NOT NULL DEFAULT 1,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    must_change_password INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    created_by INTEGER,
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    csrf_token TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip TEXT,
    user_agent TEXT
);

CREATE TABLE IF NOT EXISTS login_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    ip TEXT,
    username TEXT,
    success INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    user_id INTEGER,
    username TEXT,
    role TEXT,
    action TEXT NOT NULL,
    target TEXT,
    ip TEXT,
    success INTEGER NOT NULL,
    detail TEXT,
    prev_hash TEXT NOT NULL,
    hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    analysis_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    research_classification TEXT,
    confidence REAL,
    uncertain INTEGER,
    thumbnail_path TEXT,
    result_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_login_attempts_ip_ts ON login_attempts(ip, ts);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);
"""

# Columns added to `analyses` after v1. (name, SQL type)
_ANALYSES_ADDED_COLUMNS = (
    ("patient_id", "INTEGER"),
    ("performed_by", "INTEGER"),
    ("input_type", "TEXT"),
    ("frames_analyzed", "INTEGER"),
    ("encrypted", "INTEGER NOT NULL DEFAULT 0"),
)

_initialized: set[str] = set()


def utcnow() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def iso(dt: _dt.datetime) -> str:
    return dt.isoformat()


def parse_iso(value: str | None) -> _dt.datetime | None:
    return _dt.datetime.fromisoformat(value) if value else None


def _ensure_schema(conn: sqlite3.Connection, path: str) -> None:
    if path in _initialized:
        return
    conn.executescript(_SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(analyses)")}
    for name, sql_type in _ANALYSES_ADDED_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE analyses ADD COLUMN {name} {sql_type}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_analyses_patient ON analyses(patient_id)")
    conn.commit()
    _initialized.add(path)


@contextmanager
def connect():
    path = str(Path(settings.history_db_path))
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        _ensure_schema(conn, path)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
