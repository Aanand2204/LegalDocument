"""Password hashing and session-token logic.

Kept out of app/api/auth.py the same way document parsing lives in
document_service.py rather than in the contracts route — this module has
no FastAPI/HTTP awareness, so it's directly unit-testable and reusable.

Sessions are opaque, high-entropy tokens looked up in the database
(app/database/models.py::UserSession), not signed JWTs — there is no
secret key anywhere in this app to configure, lose, or hardcode.
"""
from __future__ import annotations

import hashlib
import secrets

import bcrypt

# bcrypt silently truncates input past 72 bytes; enforcing the limit in
# the request schema (see app/schemas/auth.py) means this is a fallback
# assertion, not the primary guard.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(f"Password exceeds bcrypt's {MAX_PASSWORD_BYTES}-byte limit")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("ascii"))
    except ValueError:
        # Malformed stored hash — treat as "does not match" rather than 500.
        return False


def generate_session_token() -> str:
    """The raw token: goes in the cookie, never in the database."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """What's actually stored/looked-up in UserSession.token_hash."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
