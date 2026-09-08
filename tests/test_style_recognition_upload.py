"""
Style recognition wired into the live upload path (D005, Batch ④): a
genuine (non-sample) uploaded photo gets a REAL CLIP prediction, persisted
via a minimal RoomAnalysis shell with unknown dimensions — distinct from
the D022 sample-room path, which uses the fixture's own labeled demo style.
"""
from __future__ import annotations

import io
import time

from PIL import Image


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _create_session(client, csrf_headers, room_type="living_room"):
    resp = client.post("/api/sessions", json={"room_type": room_type}, headers=csrf_headers())
    return resp.json["session"]["id"]


def _poll_job_to_terminal(client, job_id, timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def test_genuine_upload_gets_a_real_style_prediction(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (210, 60, 30)).save(buf, format="JPEG")
    data = {"image": (io.BytesIO(buf.getvalue()), "my_room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.json["is_sample_room"] is False
    style_job_id = resp.json["style_job_id"]
    assert style_job_id is not None
    job = _poll_job_to_terminal(client, style_job_id)
    assert job["status"] == "done", job
    assert job["stage"] == "style_recognition"

    style_resp = client.get(f"/api/sessions/{session_id}/style")
    assert style_resp.status_code == 200
    style = style_resp.json["style"]
    assert style["predicted_style"] in {
        "Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian",
    }
    assert 0.0 <= style["confidence"] <= 1.0
    assert len(style["alternatives"]) == 5
    assert "clip" in style["model_name"].lower()
    assert style_resp.json["is_sample_room"] is False
    assert style_resp.json["has_known_dimensions"] is False  # D004 unresolved for real photos


def test_sample_room_style_is_the_fixtures_labeled_demo_style_not_reclassified(client, csrf_headers):
    from ai.room_analysis.sample_rooms import SAMPLES_DIR

    _register_and_login(client)
    session_id = _create_session(client, csrf_headers, room_type="bedroom")

    with open(f"{SAMPLES_DIR}/bedroom_small_scandinavian.jpg", "rb") as f:
        sample_bytes = f.read()
    data = {"image": (io.BytesIO(sample_bytes), "bedroom_small_scandinavian.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.json["is_sample_room"] is True
    # No separate style job for a recognized sample — persist_fixture already
    # attached its labeled demo style synchronously.
    assert resp.json["style_job_id"] is None

    style_resp = client.get(f"/api/sessions/{session_id}/style")
    assert style_resp.status_code == 200
    assert style_resp.json["style"]["predicted_style"] == "Scandinavian"  # the fixture's own label
    assert style_resp.json["is_sample_room"] is True
    assert style_resp.json["has_known_dimensions"] is True  # fixture provides real dimensions


def test_style_not_found_before_any_upload(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    resp = client.get(f"/api/sessions/{session_id}/style")
    assert resp.status_code == 404


def test_second_user_cannot_read_first_users_style(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (10, 10, 200)).save(buf, format="JPEG")
    data = {"image": (io.BytesIO(buf.getvalue()), "room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, resp.json["style_job_id"])
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    assert client.get(f"/api/sessions/{session_id}/style").status_code == 404
