"""Encryption at rest for patient identifiers and stored clinical results.

Fernet (AES-128-CBC + HMAC-SHA256, authenticated) from the `cryptography` package. The key
comes from HALO_DATA_KEY, or is generated once into secrets/data.key (gitignored). Losing
that key makes stored patient data unrecoverable — back it up separately from the database.

Searching by medical record number uses a keyed HMAC "blind index" so the plaintext MRN
never has to be stored or compared.
"""
from __future__ import annotations

import hashlib
import hmac
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class DecryptionError(RuntimeError):
    pass


def _load_or_create_key() -> bytes:
    if settings.data_key:
        return settings.data_key.encode("ascii")
    path = settings.secrets_dir / "data.key"
    if path.exists():
        return path.read_bytes().strip()
    settings.secrets_dir.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    path.write_bytes(key)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass  # Windows ignores POSIX modes; rely on the user-profile ACL there.
    return key


@lru_cache(maxsize=4)
def _materials(key_source: str) -> tuple[Fernet, bytes]:
    key = _load_or_create_key()
    index_key = hmac.new(key, b"halo-scan/blind-index/v1", hashlib.sha256).digest()
    return Fernet(key), index_key


def _current() -> tuple[Fernet, bytes]:
    # Cache keyed on where the key comes from, so tests that point settings at a fresh
    # secrets dir get a fresh key instead of a stale cached one.
    return _materials(f"{settings.data_key}|{settings.secrets_dir}")


def encrypt_str(value: str | None) -> str | None:
    if value is None:
        return None
    return _current()[0].encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_str(token: str | None) -> str | None:
    if token is None:
        return None
    try:
        return _current()[0].decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken as e:
        raise DecryptionError("Stored data could not be decrypted with the current key.") from e


def blind_index(value: str) -> str:
    normalized = value.strip().upper().encode("utf-8")
    return hmac.new(_current()[1], normalized, hashlib.sha256).hexdigest()
