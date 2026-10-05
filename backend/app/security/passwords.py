"""Password hashing (Argon2id) and password policy."""
from __future__ import annotations

import secrets
import string

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.config import settings

_hasher = PasswordHasher()  # argon2id with library-recommended cost parameters

# Verified against when a username doesn't exist, so a failed login takes the same time
# whether or not the account exists (prevents username enumeration by timing).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def policy_errors(password: str, username: str | None = None) -> list[str]:
    errors = []
    if len(password) < settings.min_password_length:
        errors.append(f"Password must be at least {settings.min_password_length} characters.")
    if not any(c.isalpha() for c in password):
        errors.append("Password must contain a letter.")
    if not any(c.isdigit() for c in password):
        errors.append("Password must contain a digit.")
    if username and username.lower() in password.lower():
        errors.append("Password must not contain the username.")
    return errors


def generate_temporary_password(length: int = 14) -> str:
    alphabet = string.ascii_letters + string.digits
    while True:
        candidate = "".join(secrets.choice(alphabet) for _ in range(length))
        if not policy_errors(candidate):
            return candidate
