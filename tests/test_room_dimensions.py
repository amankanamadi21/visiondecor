"""
D004 tests (locked 2026-09-08: user-provided room dimensions). A genuine
(non-sample) photo uploaded WITH width/length should unlock full
recommendation + layout generation, not just a style prediction — this is
the actual resolution of the D004 gap left open in Batch ④.
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


def _make_jpeg_bytes(color=(90, 140, 90)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (640, 480), color).save(buf, format="JPEG")
    return buf.getvalue()


def test_real_photo_with_dimensions_unlocks_full_generation(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    data = {
        "image": (io.BytesIO(_make_jpeg_bytes()), "my_room.jpg", "image/jpeg"),
        "room_width_cm": "400",
        "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 202
    _poll_job_to_terminal(client, resp.json["style_job_id"])

    style = client.get(f"/api/sessions/{session_id}/style").json
    assert style["has_known_dimensions"] is True
    assert style["is_sample_room"] is False

    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Modern", "budget": 80000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    assert job["status"] == "done", job  # no longer room_dimensions_missing

    rec = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    assert len(rec["items"]) > 0
    layout = client.get(f"/api/sessions/{session_id}/layout").json["layout"]
    assert all(layout["constraints_satisfied"].values())


def test_only_width_without_length_is_rejected(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    data = {"image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg"), "room_width_cm": "400"}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 400


def test_out_of_range_dimension_is_rejected(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    data = {
        "image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg"),
        "room_width_cm": "5",  # below MIN_ROOM_DIMENSION_CM — likely a unit mistake (meters?)
        "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 400


def test_non_numeric_dimension_is_rejected(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    data = {
        "image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg"),
        "room_width_cm": "not-a-number",
        "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 400


def test_sample_room_ignores_any_provided_dimensions(client, csrf_headers):
    from ai.room_analysis.sample_rooms import SAMPLES_DIR

    _register_and_login(client)
    session_id = _create_session(client, csrf_headers, room_type="bedroom")

    with open(f"{SAMPLES_DIR}/bedroom_small_scandinavian.jpg", "rb") as f:
        sample_bytes = f.read()
    # Deliberately wrong dimensions — the fixture's own real ones must win.
    data = {
        "image": (io.BytesIO(sample_bytes), "bedroom_small_scandinavian.jpg", "image/jpeg"),
        "room_width_cm": "999",
        "room_length_cm": "999",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 202
    assert resp.json["is_sample_room"] is True
    assert resp.json["style_job_id"] is None  # sample path never runs the real-upload style job

    style = client.get(f"/api/sessions/{session_id}/style").json
    assert style["is_sample_room"] is True
    assert style["has_known_dimensions"] is True  # from the fixture, not the bogus 999/999
