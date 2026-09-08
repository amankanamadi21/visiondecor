"""
Sample-room recognition tests (decision D022). Uploading one of the shipped
sample images through the normal upload endpoint must auto-attach the
matching fixture's RoomAnalysis — the same mechanism a real photo goes
through, just recognized by content hash. A genuine (unrecognized) photo
must NOT trigger any fixture attachment.
"""
from __future__ import annotations

import io
import time

from PIL import Image

from ai.room_analysis.sample_rooms import SAMPLES_DIR


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _create_session(client, csrf_headers, room_type="bedroom"):
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


def test_uploading_a_sample_room_auto_attaches_its_fixture(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    with open(f"{SAMPLES_DIR}/bedroom_small_scandinavian.jpg", "rb") as f:
        sample_bytes = f.read()

    data = {"image": (io.BytesIO(sample_bytes), "bedroom_small_scandinavian.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 202
    assert resp.json["is_sample_room"] is True
    _poll_job_to_terminal(client, resp.json["job_id"])

    # No _attach_fixture / dev script needed — generate should now work
    # directly off the auto-attached RoomAnalysis.
    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Scandinavian", "budget": 60000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    assert job["status"] == "done", job

    rec = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    assert rec["is_sample_room"] is True

    layout = client.get(f"/api/sessions/{session_id}/layout").json["layout"]
    assert layout["is_sample_room"] is True


def test_uploading_a_genuine_photo_does_not_attach_any_fixture(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    buf = io.BytesIO()
    Image.new("RGB", (640, 480), (17, 200, 93)).save(buf, format="JPEG")  # not one of the shipped samples
    data = {"image": (io.BytesIO(buf.getvalue()), "my_real_room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 202
    assert resp.json["is_sample_room"] is False
    _poll_job_to_terminal(client, resp.json["job_id"])
    # Style recognition (D005/Batch ④) DOES run for a genuine photo — it's
    # the room's DIMENSIONS that stay unknown, not the analysis as a whole.
    assert resp.json["style_job_id"] is not None
    _poll_job_to_terminal(client, resp.json["style_job_id"])

    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Modern", "budget": 60000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    # A real RoomAnalysis now exists (with a genuine style prediction), but
    # its dimensions are unknown (D004 unresolved) — must fail with the
    # specific, honest room_dimensions_missing error, never a fabricated
    # layout and never a generic crash.
    assert job["status"] == "failed"
    assert job["error_code"] == "room_dimensions_missing"
