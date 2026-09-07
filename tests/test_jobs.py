"""
Job polling authorization tests — a job must only be visible to the owner
of the design_session it belongs to (brief PART 21 per-user authorization),
and a nonexistent job id must return a clean 404, not a stack trace.
"""
from __future__ import annotations

import io

from PIL import Image


def _register_and_login(client, email, password="hunter2222", name="User"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _make_jpeg_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (400, 300), (100, 120, 140)).save(buf, format="JPEG")
    return buf.getvalue()


def test_nonexistent_job_returns_404(client):
    _register_and_login(client, "alice@example.com")
    resp = client.get("/api/jobs/999999")
    assert resp.status_code == 404


def test_job_requires_authentication(client):
    resp = client.get("/api/jobs/1")
    assert resp.status_code == 401


def test_second_user_cannot_poll_first_users_job(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_resp = client.post(
        "/api/sessions", json={"room_type": "living_room"}, headers=csrf_headers()
    )
    session_id = session_resp.json["session"]["id"]
    data = {"image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg")}
    upload_resp = client.post(
        f"/api/sessions/{session_id}/image",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    job_id = upload_resp.json["job_id"]
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    resp = client.get(f"/api/jobs/{job_id}")
    assert resp.status_code == 404
