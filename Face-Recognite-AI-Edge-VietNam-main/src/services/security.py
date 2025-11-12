"""
Security helpers for password hashing and token generation.
"""

from __future__ import annotations

import hashlib
import secrets
from typing import Tuple


PBKDF2_ITERATIONS = 390_000


def hash_password(password: str, salt: str | None = None) -> Tuple[str, str]:
    """Hash a password with PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = secrets.token_hex(16)
    salt_bytes = bytes.fromhex(salt)
    pwd_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, PBKDF2_ITERATIONS)
    return pwd_hash.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """Verify a password against the stored hash."""
    candidate_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(candidate_hash, hashed)


def generate_session_token() -> str:
    """Return a random token suitable for session identifiers."""
    return secrets.token_urlsafe(32)
