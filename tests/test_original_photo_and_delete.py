"""
Two 2026-09-09 features: showing the uploaded photo alongside the generated
visualization (GET .../original-photo, and /style's original_photo_url), and
permanently deleting a design (DELETE /api/sessions/<id>), including the
filesystem cleanup a DB cascade delete alone would never do.
"""
from __future__ import annotations

import io
import os
import time

from PIL import Image
from sqlalchemy.orm import Session

from ai.room_analysis.db_adapter import persist_fixture
from ai.room_analysis.fixtures import get_fixture
from backend.db import get_engine


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    resp = client.post("/api/auth/register", json={"email": email, "password": password, "name": name})
    if resp.status_code >= 400:
        # Already registered earlier in this test (e.g. logging back in as
        # the first user after a second user's session) — log in instead.
        client.post("/api/auth/login", json={"email": email, "password": password})


def _create_session(client, csrf_headers, room_type="living_room"):
    resp = client.post("/api/sessions", json={"room_type": room_type}, headers=csrf_headers())
    return resp.json["session"]["id"]


def _make_jpeg_bytes(color=(90, 140, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


def _poll_job_to_terminal(client, job_id, timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def _upload_real_photo(client, csrf_headers, session_id, wait_for_style=False):
    photo_bytes = _make_jpeg_bytes()
    data = {"image": (io.BytesIO(photo_bytes), "room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 202, resp.json
    if wait_for_style:
        _poll_job_to_terminal(client, resp.json["style_job_id"], timeout_s=60)
    return photo_bytes


# --- Original photo ---

def test_original_photo_requires_auth(client):
    resp = client.get("/api/sessions/1/original-photo")
    assert resp.status_code == 401


def test_original_photo_serves_the_real_uploaded_bytes(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    photo_bytes = _upload_real_photo(client, csrf_headers, session_id, wait_for_style=True)

    resp = client.get(f"/api/sessions/{session_id}/original-photo")
    assert resp.status_code == 200
    assert resp.data == photo_bytes

    style = client.get(f"/api/sessions/{session_id}/style").json
    assert style["original_photo_url"] == f"/api/sessions/{session_id}/original-photo"


def test_sample_room_original_photo_is_a_static_asset_not_the_authenticated_endpoint(client, csrf_headers, app):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers, room_type="bedroom")
    with app.app_context():
        with Session(get_engine()) as db:
            persist_fixture(db, session_id, get_fixture("bedroom_small_scandinavian"))

    style = client.get(f"/api/sessions/{session_id}/style").json
    assert style["original_photo_url"] == "/samples/bedroom_small_scandinavian.jpg"

    # The authenticated endpoint must not serve a fixture's fake "FIXTURE:" path.
    resp = client.get(f"/api/sessions/{session_id}/original-photo")
    assert resp.status_code == 404


def test_second_user_cannot_fetch_first_users_original_photo(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    _upload_real_photo(client, csrf_headers, session_id)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    resp = client.get(f"/api/sessions/{session_id}/original-photo")
    assert resp.status_code == 404


# --- Delete session ---

def test_delete_requires_auth(client):
    resp = client.delete("/api/sessions/1")
    assert resp.status_code == 401


def test_owner_can_delete_own_session(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    resp = client.delete(f"/api/sessions/{session_id}", headers=csrf_headers())
    assert resp.status_code == 204

    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_second_user_cannot_delete_first_users_session(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    resp = client.delete(f"/api/sessions/{session_id}", headers=csrf_headers())
    assert resp.status_code == 404

    # Confirm it's untouched — Alice must still be able to see it.
    client.post("/api/auth/logout")
    _register_and_login(client, "alice@example.com")
    assert client.get(f"/api/sessions/{session_id}").status_code == 200


def test_delete_removes_the_uploaded_photo_file_from_disk(client, csrf_headers, app):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    _upload_real_photo(client, csrf_headers, session_id)

    with app.app_context():
        with Session(get_engine()) as db:
            from backend.models.room import RoomImage

            room_image = db.query(RoomImage).filter_by(session_id=session_id).first()
            original_path = os.path.abspath(room_image.original_path)
    assert os.path.exists(original_path)

    resp = client.delete(f"/api/sessions/{session_id}", headers=csrf_headers())
    assert resp.status_code == 204
    assert not os.path.exists(original_path)
