"""Analysis history storage — SQLite, no ORM, no personal identifiers (spec section 23).

Only what's needed to render a history list: id, timestamp, quality status, result label,
confidence, uncertainty flag, and a thumbnail path. No names, no device identifiers beyond
what's harmless for debugging.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

_SCHEMA = """
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
"""


@contextmanager
def _connect():
    conn = sqlite3.connect(str(settings.history_db_path))
    try:
        conn.execute(_SCHEMA)
        yield conn
        conn.commit()
    finally:
        conn.close()


def save_analysis(
    analysis_id: str, timestamp: str, quality_status: str,
    research_classification: str | None, confidence: float | None, uncertain: bool | None,
    thumbnail_path: str | None, result_json: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyses "
            "(analysis_id, timestamp, quality_status, research_classification, confidence, "
            "uncertain, thumbnail_path, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (analysis_id, timestamp, quality_status, research_classification, confidence,
             int(bool(uncertain)) if uncertain is not None else None, thumbnail_path, result_json),
        )


def get_analysis(analysis_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.execute("SELECT result_json FROM analyses WHERE analysis_id = ?", (analysis_id,))
        row = cur.fetchone()
        if row is None:
            return None
        import json
        return json.loads(row[0])


def list_history(limit: int = 50) -> list[dict]:
    with _connect() as conn:
        cur = conn.execute(
            "SELECT analysis_id, timestamp, quality_status, research_classification, "
            "confidence, uncertain FROM analyses ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cur.fetchall()
    return [
        {
            "analysis_id": r[0], "timestamp": r[1], "quality_status": r[2],
            "research_classification": r[3], "confidence": r[4],
            "uncertain": bool(r[5]) if r[5] is not None else None,
        }
        for r in rows
    ]
