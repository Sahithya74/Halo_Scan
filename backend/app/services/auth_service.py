"""Login, lockout and password changes."""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass

from app.config import settings
from app.db import connect, iso, parse_iso, utcnow
from app.security import audit
from app.security.passwords import hash_password, needs_rehash, policy_errors, verify_password


@dataclass
class LoginResult:
    ok: bool
    user: dict | None = None
    error: str | None = None  # "invalid" | "locked" | "rate_limited"
    retry_after_minutes: int | None = None


def _record_attempt(conn, ip: str | None, username: str, success: bool) -> None:
    conn.execute(
        "INSERT INTO login_attempts (ts, ip, username, success) VALUES (?, ?, ?, ?)",
        (iso(utcnow()), ip, username[:64], int(success)),
    )


def _ip_rate_limited(conn, ip: str | None) -> bool:
    if not ip:
        return False
    since = iso(utcnow() - _dt.timedelta(minutes=settings.lockout_minutes))
    count = conn.execute(
        "SELECT COUNT(*) FROM login_attempts WHERE ip = ? AND success = 0 AND ts >= ?", (ip, since)
    ).fetchone()[0]
    return count >= settings.ip_max_failed_logins


def authenticate(username: str, password: str, ip: str | None) -> LoginResult:
    username = (username or "").strip()
    now = utcnow()
    with connect() as conn:
        if _ip_rate_limited(conn, ip):
            _record_attempt(conn, ip, username, False)
            result = LoginResult(ok=False, error="rate_limited", retry_after_minutes=settings.lockout_minutes)
        else:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            locked_until = parse_iso(row["locked_until"]) if row else None
            if row is not None and locked_until and locked_until > now:
                verify_password(None, password)  # keep timing uniform
                _record_attempt(conn, ip, username, False)
                minutes = int((locked_until - now).total_seconds() // 60) + 1
                result = LoginResult(ok=False, error="locked", retry_after_minutes=minutes)
            elif row is None or not row["active"] or not verify_password(row["password_hash"], password):
                if row is None:
                    verify_password(None, password)
                _record_attempt(conn, ip, username, False)
                result = LoginResult(ok=False, error="invalid")
                if row is not None and row["active"]:
                    failed = row["failed_attempts"] + 1
                    if failed >= settings.max_failed_logins:
                        until = now + _dt.timedelta(minutes=settings.lockout_minutes)
                        conn.execute("UPDATE users SET failed_attempts = 0, locked_until = ? WHERE id = ?",
                                     (iso(until), row["id"]))
                        result = LoginResult(ok=False, error="locked", retry_after_minutes=settings.lockout_minutes)
                    else:
                        conn.execute("UPDATE users SET failed_attempts = ? WHERE id = ?", (failed, row["id"]))
            else:
                _record_attempt(conn, ip, username, True)
                updates = {"failed_attempts": 0, "locked_until": None, "last_login_at": iso(now)}
                if needs_rehash(row["password_hash"]):
                    updates["password_hash"] = hash_password(password)
                conn.execute(
                    "UPDATE users SET " + ", ".join(f"{k} = ?" for k in updates) + " WHERE id = ?",
                    (*updates.values(), row["id"]),
                )
                result = LoginResult(ok=True, user={
                    "id": row["id"], "username": row["username"], "role": row["role"],
                    "patient_id": row["patient_id"],
                    "must_change_password": bool(row["must_change_password"]),
                })

    audit.record(
        "login" if result.ok else f"login_failed:{result.error}",
        user_id=result.user["id"] if result.user else None, username=username[:64],
        role=result.user["role"] if result.user else None, ip=ip, success=result.ok,
    )
    return result


def change_password(user_id: int, username: str, current: str, new: str) -> list[str]:
    with connect() as conn:
        row = conn.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
    if row is None or not verify_password(row["password_hash"], current):
        return ["Current password is incorrect."]
    errors = policy_errors(new, username)
    if new == current:
        errors.append("New password must differ from the current one.")
    if errors:
        return errors
    with connect() as conn:
        conn.execute("UPDATE users SET password_hash = ?, must_change_password = 0 WHERE id = ?",
                     (hash_password(new), user_id))
    return []
