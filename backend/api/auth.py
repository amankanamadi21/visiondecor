"""
Auth routes — FR-1 (registration + login), decision D014 (JWT in httpOnly
cookie + CSRF double-submit).
"""
from __future__ import annotations

import re

from flask import Blueprint, current_app, g, jsonify, request

from backend.db import get_session
from backend.errors import conflict, unauthorized, validation_error
from backend.models import User
from backend.services.auth_service import (
    generate_csrf_token,
    hash_password,
    issue_access_token,
    verify_password,
)
from backend.utils.auth_decorators import login_required

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _set_auth_cookies(response, user_id: int):
    config = current_app.config["VD_CONFIG"]
    token = issue_access_token(user_id, config.JWT_SECRET_KEY, config.JWT_ACCESS_TOKEN_EXPIRES_MINUTES)
    csrf_token = generate_csrf_token()

    response.set_cookie(
        config.JWT_COOKIE_NAME,
        token,
        httponly=True,
        secure=config.JWT_COOKIE_SECURE,
        samesite="Lax",
        max_age=config.JWT_ACCESS_TOKEN_EXPIRES_MINUTES * 60,
    )
    # CSRF cookie is intentionally NOT httpOnly — the frontend JS must read it
    # and echo it back in the X-CSRF-Token header (double-submit pattern).
    response.set_cookie(
        config.CSRF_COOKIE_NAME,
        csrf_token,
        httponly=False,
        secure=config.JWT_COOKIE_SECURE,
        samesite="Lax",
        max_age=config.JWT_ACCESS_TOKEN_EXPIRES_MINUTES * 60,
    )
    return response


def _user_public_dict(user: User) -> dict:
    return {"id": user.id, "email": user.email, "name": user.name}


@bp.post("/register")
def register():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    name = (data.get("name") or "").strip()

    if not EMAIL_RE.match(email):
        raise validation_error("Please provide a valid email address.", {"field": "email"})
    if len(password) < 8:
        raise validation_error("Password must be at least 8 characters.", {"field": "password"})
    if not name:
        raise validation_error("Please provide your name.", {"field": "name"})

    db = get_session()
    if db.query(User).filter_by(email=email).first() is not None:
        raise conflict("An account with this email already exists.", {"field": "email"})

    user = User(email=email, password_hash=hash_password(password), name=name)
    db.add(user)
    db.commit()

    response = jsonify({"user": _user_public_dict(user)})
    return _set_auth_cookies(response, user.id), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = get_session()
    user = db.query(User).filter_by(email=email).first()
    # Deliberately identical error for "no such user" and "wrong password" —
    # do not leak which one it was.
    if user is None or not verify_password(password, user.password_hash):
        raise unauthorized("Incorrect email or password.")

    response = jsonify({"user": _user_public_dict(user)})
    return _set_auth_cookies(response, user.id)


@bp.post("/logout")
def logout():
    config = current_app.config["VD_CONFIG"]
    response = jsonify({"ok": True})
    response.delete_cookie(config.JWT_COOKIE_NAME)
    response.delete_cookie(config.CSRF_COOKIE_NAME)
    return response


@bp.get("/me")
@login_required
def me():
    return jsonify({"user": _user_public_dict(g.user)})
