"""
Upload validation tests (brief PART 15/21): a valid image is accepted and
enqueues a job; a renamed non-image is rejected by magic-byte inspection,
not by trusting the filename/Content-Type; an oversized file is rejected
before it is fully processed; a second user cannot upload into a session
they don't own.
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


def _make_jpeg_bytes(size=(800, 600), color=(120, 140, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="JPEG")
    return buf.getvalue()


def test_valid_image_upload_creates_room_image_and_job(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    data = {"image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )

    assert resp.status_code == 202
    assert resp.json["room_image"]["width"] == 800
    assert resp.json["room_image"]["height"] == 600
    job_id = resp.json["job_id"]
    assert job_id is not None

    # Poll until the background preprocess job finishes (or time out loudly —
    # a stuck job here indicates a real bug, not something to paper over).
    for _ in range(50):
        job_resp = client.get(f"/api/jobs/{job_id}")
        assert job_resp.status_code == 200
        if job_resp.json["job"]["status"] in ("done", "failed"):
            break
        time.sleep(0.1)
    assert job_resp.json["job"]["status"] == "done", job_resp.json["job"]
    assert job_resp.json["job"]["progress"] == 100
    assert job_resp.json["job"]["stage"] == "preprocess"


def test_renamed_text_file_is_rejected_by_magic_bytes(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    fake_image = io.BytesIO(b"this is definitely not an image, just plain text " * 20)
    data = {"image": (fake_image, "room.jpg", "image/jpeg")}  # lies about both name and content-type
    resp = client.post(
        f"/api/sessions/{session_id}/image",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )

    assert resp.status_code == 415
    assert resp.json["error"]["code"] == "unsupported_media"


def test_oversized_image_is_rejected(client, app, csrf_headers):
    app.config["VD_CONFIG"].MAX_UPLOAD_SIZE_MB = 1  # tighten limit for this test only
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    oversized = io.BytesIO(b"\xff\xd8\xff" + os_urandom(2 * 1024 * 1024))  # ~2MB, JPEG magic prefix
    data = {"image": (oversized, "big.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )

    assert resp.status_code == 413
    assert resp.json["error"]["code"] == "payload_too_large"


def os_urandom(n):
    import os

    return os.urandom(n)


def test_cannot_upload_into_another_users_session(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    data = {"image": (io.BytesIO(_make_jpeg_bytes()), "room.jpg", "image/jpeg")}
    resp = client.post(
        f"/api/sessions/{session_id}/image",
        data=data,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    assert resp.status_code == 404


def test_uploading_same_image_twice_dedupes_by_hash(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    payload = _make_jpeg_bytes()

    data1 = {"image": (io.BytesIO(payload), "room.jpg", "image/jpeg")}
    resp1 = client.post(
        f"/api/sessions/{session_id}/image",
        data=data1,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    data2 = {"image": (io.BytesIO(payload), "room_again.jpg", "image/jpeg")}
    resp2 = client.post(
        f"/api/sessions/{session_id}/image",
        data=data2,
        content_type="multipart/form-data",
        headers=csrf_headers(),
    )

    assert resp1.json["room_image"]["id"] == resp2.json["room_image"]["id"]
