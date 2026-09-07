"""
@login_required — verifies the JWT cookie, loads the User, enforces CSRF on
state-changing methods, and exposes the authenticated user as flask.g.user.

Per-user authorization for individual resources (e.g. "does this session
belong to this user?") is a separate, explicit check done in each route —
this decorator only proves *who* is calling, not *what* they may access.
"""
from __future__ import annotations

from functools import wraps

import jwt
from flask import current_app, g, request

from backend.db import get_session
from backend.errors import forbidden, unauthorized
from backend.services.auth_service import decode_access_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        from backend.models import User  # local import avoids a circular import at module load time

        config = current_app.config["VD_CONFIG"]
        token = request.cookies.get(config.JWT_COOKIE_NAME)
        if not token:
            raise unauthorized("Please log in to continue.")

        try:
            payload = decode_access_token(token, config.JWT_SECRET_KEY)
        except jwt.ExpiredSignatureError:
            raise unauthorized("Your session has expired. Please log in again.")
        except jwt.PyJWTError:
            raise unauthorized("Invalid session. Please log in again.")

        if request.method not in SAFE_METHODS:
            csrf_cookie = request.cookies.get(config.CSRF_COOKIE_NAME)
            csrf_header = request.headers.get("X-CSRF-Token")
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                raise forbidden("CSRF validation failed. Please refresh and try again.")

        db = get_session()
        user = db.get(User, int(payload["sub"]))
        if user is None:
            raise unauthorized("Account no longer exists.")

        g.user = user
        return fn(*args, **kwargs)

    return wrapper
