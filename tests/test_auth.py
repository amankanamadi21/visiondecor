"""
Auth flow tests — FR-1, decision D014 (JWT in httpOnly cookie + CSRF).
"""
from __future__ import annotations


def _register(client, email="alice@example.com", password="hunter2222", name="Alice"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def test_register_creates_user_and_sets_httponly_cookie(client):
    resp = _register(client)
    assert resp.status_code == 201
    assert resp.json["user"]["email"] == "alice@example.com"

    # Inspect the Set-Cookie headers directly — this is what proves the JWT
    # is httpOnly (unreadable from JS) rather than merely "an implementation
    # detail we assume is correct".
    set_cookie_headers = resp.headers.get_all("Set-Cookie")
    auth_cookie = next(h for h in set_cookie_headers if h.startswith("vd_access_token="))
    csrf_cookie = next(h for h in set_cookie_headers if h.startswith("vd_csrf_token="))
    assert "HttpOnly" in auth_cookie
    assert "HttpOnly" not in csrf_cookie  # CSRF cookie must be JS-readable by design


def test_register_rejects_weak_password(client):
    resp = _register(client, password="short")
    assert resp.status_code == 400
    assert resp.json["error"]["code"] == "validation_error"


def test_register_rejects_duplicate_email(client):
    _register(client)
    resp = _register(client)
    assert resp.status_code == 409
    assert resp.json["error"]["code"] == "conflict"


def test_login_with_correct_credentials_succeeds(client):
    _register(client)
    resp = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "hunter2222"})
    assert resp.status_code == 200
    assert resp.json["user"]["email"] == "alice@example.com"


def test_login_with_wrong_password_returns_401_without_leaking_which_field(client):
    _register(client)
    resp = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "wrongpass"})
    assert resp.status_code == 401
    resp2 = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "wrongpass"})
    assert resp2.status_code == 401
    assert resp.json["error"]["message"] == resp2.json["error"]["message"]


def test_me_requires_authentication(client):
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json["error"]["code"] == "unauthorized"


def test_me_returns_current_user_after_login(client):
    _register(client)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json["user"]["email"] == "alice@example.com"


def test_logout_clears_cookies(client):
    _register(client)
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200
    resp2 = client.get("/api/auth/me")
    assert resp2.status_code == 401
