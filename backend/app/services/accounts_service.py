"""User accounts and patient records. Patient identifiers are encrypted at rest."""
from __future__ import annotations

import re
import secrets
import sqlite3
import string

from app.db import connect, iso, utcnow
from app.security.crypto import blind_index, decrypt_str, encrypt_str
from app.security.passwords import generate_temporary_password, hash_password, policy_errors
from app.security.sessions import revoke_user_sessions

ROLES = ("admin", "doctor", "nurse", "patient")
_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


class AccountError(ValueError):
    pass


def _validate_username(username: str) -> str:
    username = username.strip()
    if not _USERNAME_RE.match(username):
        raise AccountError("Username must be 3-32 characters: letters, digits, '.', '_' or '-'.")
    return username


def create_user(
    username: str, password: str, role: str, display_name: str | None, created_by: int | None,
    patient_id: int | None = None, must_change_password: bool = False,
) -> int:
    if role not in ROLES:
        raise AccountError(f"Unknown role: {role}")
    username = _validate_username(username)
    errors = policy_errors(password, username)
    if errors:
        raise AccountError(" ".join(errors))
    try:
        with connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (username, password_hash, role, display_name_enc, patient_id, "
                "must_change_password, created_at, created_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (username, hash_password(password), role, encrypt_str(display_name), patient_id,
                 int(must_change_password), iso(utcnow()), created_by),
            )
            return cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise AccountError("That username is already taken.") from e


def _user_dict(row) -> dict:
    return {
        "id": row["id"], "username": row["username"], "role": row["role"],
        "display_name": decrypt_str(row["display_name_enc"]), "active": bool(row["active"]),
        "patient_id": row["patient_id"], "must_change_password": bool(row["must_change_password"]),
        "locked_until": row["locked_until"], "created_at": row["created_at"],
        "last_login_at": row["last_login_at"],
    }


def get_user(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user_dict(row) if row else None


def list_users(role: str | None = None) -> list[dict]:
    with connect() as conn:
        if role:
            rows = conn.execute("SELECT * FROM users WHERE role = ? ORDER BY id", (role,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM users ORDER BY id").fetchall()
    return [_user_dict(r) for r in rows]


def set_active(user_id: int, active: bool) -> None:
    with connect() as conn:
        conn.execute("UPDATE users SET active = ? WHERE id = ?", (int(active), user_id))
    if not active:
        revoke_user_sessions(user_id)


def reset_password(user_id: int) -> str:
    temp = generate_temporary_password()
    with connect() as conn:
        conn.execute(
            "UPDATE users SET password_hash = ?, must_change_password = 1, failed_attempts = 0, "
            "locked_until = NULL WHERE id = ?",
            (hash_password(temp), user_id),
        )
    revoke_user_sessions(user_id)
    return temp


def count_admins() -> int:
    with connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND active = 1").fetchone()[0]


# ---------------- patients ----------------

def _new_patient_code() -> str:
    alphabet = string.ascii_uppercase + string.digits
    return "PT-" + "".join(secrets.choice(alphabet) for _ in range(6))


def _patient_dict(row) -> dict:
    return {
        "id": row["id"], "patient_code": row["patient_code"], "mrn": decrypt_str(row["mrn_enc"]),
        "name": decrypt_str(row["name_enc"]), "dob": decrypt_str(row["dob_enc"]), "sex": row["sex"],
        "created_at": row["created_at"],
    }


def register_patient(
    mrn: str, name: str, dob: str | None, sex: str | None, created_by: int, create_login: bool = True,
) -> dict:
    mrn, name = mrn.strip(), name.strip()
    if not mrn or not name:
        raise AccountError("Medical record number and name are required.")
    if sex not in (None, "", "F", "M", "X"):
        raise AccountError("Sex must be F, M or X.")
    try:
        with connect() as conn:
            code = _new_patient_code()
            cur = conn.execute(
                "INSERT INTO patients (patient_code, mrn_index, mrn_enc, name_enc, dob_enc, sex, "
                "created_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (code, blind_index(mrn), encrypt_str(mrn), encrypt_str(name),
                 encrypt_str(dob) if dob else None, sex or None, created_by, iso(utcnow())),
            )
            patient_id = cur.lastrowid
    except sqlite3.IntegrityError as e:
        raise AccountError("A patient with that medical record number already exists.") from e

    result = {"patient": get_patient(patient_id), "login": None}
    if create_login:
        username = code.lower()
        temp = generate_temporary_password()
        create_user(username, temp, "patient", name, created_by, patient_id=patient_id,
                    must_change_password=True)
        result["login"] = {"username": username, "temporary_password": temp}
    return result


def get_patient(patient_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
    return _patient_dict(row) if row else None


def find_patient_by_mrn(mrn: str) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE mrn_index = ?", (blind_index(mrn),)).fetchone()
    return _patient_dict(row) if row else None


def list_patients(query: str | None = None) -> list[dict]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM patients ORDER BY id DESC").fetchall()
    patients = [_patient_dict(r) for r in rows]
    if query:
        q = query.strip().lower()
        patients = [p for p in patients
                    if q in p["name"].lower() or q in p["patient_code"].lower() or q == p["mrn"].lower()]
    return patients
