"""
Password hashing (argon2) and JWT issuance/verification (decision D014).

JWT is delivered in an httpOnly cookie rather than returned in the response
body / stored in localStorage, so it is unreadable from JavaScript and safe
against XSS token theft (brief PART 21). A separate, non-httpOnly CSRF
cookie is issued alongside it; state-changing requests must echo its value
in an `X-CSRF-Token` header (double-submit cookie pattern) so a cross-site
request cannot ride on the auth cookie alone.
"""
from __future__ import annotations

import secrets
import time
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(plain_password: str) -> str:
    return _hasher.hash(plain_password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, plain_password)
    except VerifyMismatchError:
        return False
    except Exception:
        # Any other argon2 error (e.g. malformed hash) is treated as a
        # verification failure, never as an exception that leaks internals.
        return False


def issue_access_token(user_id: int, secret_key: str, expires_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    return jwt.encode(payload, secret_key, algorithm="HS256")


def decode_access_token(token: str, secret_key: str) -> dict:
    """Raises jwt.PyJWTError subclasses on invalid/expired tokens — callers
    (the @login_required decorator) are responsible for turning that into a
    401 ApiError rather than letting it bubble up as an unhandled exception."""
    return jwt.decode(token, secret_key, algorithms=["HS256"])


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)
