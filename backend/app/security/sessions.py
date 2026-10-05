"""Server-side sessions.

The browser only ever holds a random opaque token (HttpOnly cookie); the database stores its
SHA-256, so a leaked database cannot be replayed as live sessions. Sessions expire after
`session_idle_minutes` without activity and after `session_absolute_hours` regardless.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import secrets
from dataclasses import dataclass

from app.config import settings
from app.db import connect, iso, parse_iso, utcnow


@dataclass
class SessionInfo:
    token_hash: str
    user_id: int
    username: str
    role: str
    patient_id: int | None
    must_change_password: bool
    csrf_token: str


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def create_session(user_id: int, ip: str | None, user_agent: str | None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    now = utcnow()
    expires = now + _dt.timedelta(hours=settings.session_absolute_hours)
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (token_hash, user_id, csrf_token, created_at, last_seen, "
            "expires_at, ip, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (_hash(token), user_id, csrf, iso(now), iso(now), iso(expires), ip, (user_agent or "")[:200]),
        )
    return token, csrf


def get_session(token: str | None) -> SessionInfo | None:
    if not token:
        return None
    token_hash = _hash(token)
    now = utcnow()
    with connect() as conn:
        row = conn.execute(
            "SELECT s.token_hash, s.user_id, s.csrf_token, s.last_seen, s.expires_at, "
            "u.username, u.role, u.patient_id, u.must_change_password, u.active "
            "FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        idle_limit = parse_iso(row["last_seen"]) + _dt.timedelta(minutes=settings.session_idle_minutes)
        if not row["active"] or now > parse_iso(row["expires_at"]) or now > idle_limit:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None
        conn.execute("UPDATE sessions SET last_seen = ? WHERE token_hash = ?", (iso(now), token_hash))
    return SessionInfo(
        token_hash=token_hash, user_id=row["user_id"], username=row["username"], role=row["role"],
        patient_id=row["patient_id"], must_change_password=bool(row["must_change_password"]),
        csrf_token=row["csrf_token"],
    )


def revoke_session(token: str | None) -> None:
    if token:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (_hash(token),))


def revoke_user_sessions(user_id: int, keep_token_hash: str | None = None) -> None:
    with connect() as conn:
        if keep_token_hash:
            conn.execute("DELETE FROM sessions WHERE user_id = ? AND token_hash != ?", (user_id, keep_token_hash))
        else:
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))
