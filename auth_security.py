"""Password hashing and URL-safe token helpers for CogniSweep auth."""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from typing import Optional


LOGGER = logging.getLogger(__name__)
PASSWORD_HASH_ITERATIONS = 260_000


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def b64url_decode(data: str) -> bytes:
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + pad)


def hash_password(password: str, salt: Optional[str] = None, iterations: int = PASSWORD_HASH_ITERATIONS) -> str:
    salt = salt or b64url(os.urandom(16))
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    return f"pbkdf2_sha256${iterations}${salt}${b64url(digest)}"


def verify_password(password: str, stored_hash: str) -> bool:
    parts = str(stored_hash or "").split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), parts[2].encode("utf-8"), iterations)
        return hmac.compare_digest(b64url(digest), parts[3])
    except Exception as exc:
        LOGGER.warning("Password hash verification failed: %s", exc)
        return False
