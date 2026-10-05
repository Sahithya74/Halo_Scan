"""Analysis history. Full results are encrypted at rest; only the fields needed to list
and filter history (label, confidence, status, owner) are kept in the clear.
"""
from __future__ import annotations

import json

from app.db import connect
from app.security.crypto import decrypt_str, encrypt_str


def save_analysis(
    analysis_id: str, timestamp: str, quality_status: str,
    research_classification: str | None, confidence: float | None, uncertain: bool | None,
    result: dict, patient_id: int | None = None, performed_by: int | None = None,
    input_type: str = "image", frames_analyzed: int | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO analyses (analysis_id, timestamp, quality_status, "
            "research_classification, confidence, uncertain, thumbnail_path, result_json, "
            "patient_id, performed_by, input_type, frames_analyzed, encrypted) "
            "VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?, 1)",
            (analysis_id, timestamp, quality_status, research_classification, confidence,
             int(bool(uncertain)) if uncertain is not None else None,
             encrypt_str(json.dumps(result)), patient_id, performed_by, input_type, frames_analyzed),
        )


def _decode(row) -> dict:
    raw = row["result_json"]
    return json.loads(decrypt_str(raw) if row["encrypted"] else raw)


def get_analysis(analysis_id: str) -> dict | None:
    """Returns {"patient_id": ..., "result": {...}} or None."""
    with connect() as conn:
        row = conn.execute(
            "SELECT result_json, encrypted, patient_id FROM analyses WHERE analysis_id = ?", (analysis_id,)
        ).fetchone()
    if row is None:
        return None
    return {"patient_id": row["patient_id"], "result": _decode(row)}


def list_history(limit: int = 50, patient_id: int | None = None) -> list[dict]:
    sql = ("SELECT analysis_id, timestamp, quality_status, research_classification, confidence, "
           "uncertain, patient_id, input_type FROM analyses")
    params: tuple = ()
    if patient_id is not None:
        sql += " WHERE patient_id = ?"
        params = (patient_id,)
    sql += " ORDER BY timestamp DESC LIMIT ?"
    with connect() as conn:
        rows = conn.execute(sql, (*params, limit)).fetchall()
    return [
        {
            "analysis_id": r["analysis_id"], "timestamp": r["timestamp"],
            "quality_status": r["quality_status"], "research_classification": r["research_classification"],
            "confidence": r["confidence"], "uncertain": bool(r["uncertain"]) if r["uncertain"] is not None else None,
            "patient_id": r["patient_id"], "input_type": r["input_type"] or "image",
        }
        for r in rows
    ]


def encrypt_legacy_rows() -> int:
    """Encrypts results stored in plaintext by pre-v2 versions. Idempotent."""
    with connect() as conn:
        rows = conn.execute("SELECT analysis_id, result_json FROM analyses WHERE encrypted = 0").fetchall()
        for r in rows:
            conn.execute("UPDATE analyses SET result_json = ?, encrypted = 1 WHERE analysis_id = ?",
                         (encrypt_str(r["result_json"]), r["analysis_id"]))
    return len(rows)


def class_counts() -> dict[str, int]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT COALESCE(research_classification, quality_status) AS k, COUNT(*) AS n "
            "FROM analyses GROUP BY k"
        ).fetchall()
    return {r["k"]: r["n"] for r in rows}
