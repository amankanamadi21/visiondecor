"""
Design session tests — FR-1/FR-8, and the per-user authorization boundary
that login_required alone does not provide (brief NFR-2/PART 21).
"""
from __future__ import annotations


def _register_and_login(client, email, password="hunter2222", name="User"):
    return client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def test_create_session_requires_auth(client):
    resp = client.post("/api/sessions", json={"room_type": "living_room"})
    assert resp.status_code == 401


def test_create_and_fetch_own_session(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    create_resp = client.post(
        "/api/sessions",
        json={"room_type": "living_room", "title": "My Living Room"},
        headers=csrf_headers(),
    )
    assert create_resp.status_code == 201
    session_id = create_resp.json["session"]["id"]

    get_resp = client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 200
    assert get_resp.json["session"]["room_type"] == "living_room"
    assert get_resp.json["session"]["status"] == "draft"


def test_rejects_invalid_room_type(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    resp = client.post("/api/sessions", json={"room_type": "spaceship"}, headers=csrf_headers())
    assert resp.status_code == 400


def test_second_user_cannot_fetch_first_users_session(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    create_resp = client.post("/api/sessions", json={"room_type": "bedroom"}, headers=csrf_headers())
    session_id = create_resp.json["session"]["id"]
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com")
    resp = client.get(f"/api/sessions/{session_id}")
    # 404, not 403 — must not confirm to Bob that Alice's session id exists.
    assert resp.status_code == 404


def test_list_sessions_only_returns_own(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    client.post("/api/sessions", json={"room_type": "bedroom"}, headers=csrf_headers())
    client.post("/api/sessions", json={"room_type": "office"}, headers=csrf_headers())
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com")
    client.post("/api/sessions", json={"room_type": "study_room"}, headers=csrf_headers())

    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    assert len(resp.json["sessions"]) == 1
    assert resp.json["sessions"][0]["room_type"] == "study_room"
