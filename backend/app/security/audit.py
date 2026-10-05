"""Tamper-evident audit log.

Every row stores the SHA-256 of (previous row's hash + this row's content), forming a
chain. Editing or deleting any past row breaks every hash after it, which verify_chain()
detects. This doesn't stop someone with database write access from rewriting the whole
chain, but it does make silent edits to individual records detectable.
"""
from __future__ import annotations

import hashlib
import json

from app.db import connect, iso, utcnow

GENESIS_HASH = "0" * 64


def _row_hash(prev_hash: str, fields: list) -> str:
    payload = prev_hash + json.dumps(fields, separators=(",", ":"), sort_keys=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def record(
    action: str, *, user_id: int | None = None, username: str | None = None, role: str | None = None,
    target: str | None = None, ip: str | None = None, success: bool = True, detail: str | None = None,
) -> None:
    ts = iso(utcnow())
    fields = [ts, user_id, username, role, action, target, ip, int(success), detail]
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")  # serialize writers so the chain can't fork
        last = conn.execute("SELECT hash FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        prev_hash = last["hash"] if last else GENESIS_HASH
        conn.execute(
            "INSERT INTO audit_log (ts, user_id, username, role, action, target, ip, success, "
            "detail, prev_hash, hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*fields, prev_hash, _row_hash(prev_hash, fields)),
        )


def verify_chain() -> dict:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, user_id, username, role, action, target, ip, success, detail, "
            "prev_hash, hash FROM audit_log ORDER BY id"
        ).fetchall()
    expected_prev = GENESIS_HASH
    for row in rows:
        fields = [row["ts"], row["user_id"], row["username"], row["role"], row["action"],
                  row["target"], row["ip"], row["success"], row["detail"]]
        if row["prev_hash"] != expected_prev or row["hash"] != _row_hash(expected_prev, fields):
            return {"verified": False, "entries_checked": len(rows), "first_broken_id": row["id"]}
        expected_prev = row["hash"]
    return {"verified": True, "entries_checked": len(rows), "first_broken_id": None}


def list_entries(limit: int = 100, offset: int = 0) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT id, ts, username, role, action, target, ip, success, detail FROM audit_log "
            "ORDER BY id DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
    return [dict(r) | {"success": bool(r["success"])} for r in rows]
