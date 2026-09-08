"""
User-confirmed real geometry for a detected item (2026-09-08 decision:
"optional, from the results page"). The one exception to "a detection never
gets a real (x, y) position or exact size" (tests/test_real_cv_detection.py):
every number here is explicitly user-provided, not derived from the pixel
bbox, which is what makes it honest enough to place as a real existing
object in the layout.
"""
from __future__ import annotations

import io
import os
import time

import pytest
from sqlalchemy.orm import Session

from ai.recommendation.scoring import DEFAULT_FREE_SPACE_RATIO
from ai.room_analysis.db_adapter import (
    LoadedAnalysis,
    UnconfirmableDetectionError,
    confirm_detected_object_geometry,
    load_room_model_from_db,
)
from backend.db import get_engine
from backend.models.room import DetectedObject, DetectionSource, RoomAnalysis, RoomImage, ScaleSource
from backend.models.session import DesignSession
from backend.models.user import User

REAL_PHOTO = "datasets/houzz_styles/dataset_test/dataset_test/contemporary/contemporary_118.jpg"
requires_dataset = pytest.mark.skipif(
    not os.path.exists(REAL_PHOTO), reason="Houzz dataset not present in this environment"
)


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _create_session(client, csrf_headers, room_type="living_room"):
    resp = client.post("/api/sessions", json={"room_type": room_type}, headers=csrf_headers())
    return resp.json["session"]["id"]


def _poll_job_to_terminal(client, job_id, timeout_s=60):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.2)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def _make_analysis_with_detection(db, *, class_label="couch", confidence=0.9, room_width_cm=400.0, room_length_cm=500.0):
    """Bare DB fixture — no real model call — for testing the pure
    confirm/load logic in isolation from detection/segmentation itself."""
    user = User(email=f"geom-{class_label}-{confidence}@test.com", password_hash="x", name="Geom Test")
    db.add(user)
    db.flush()
    design_session = DesignSession(user_id=user.id, room_type="living_room")
    db.add(design_session)
    db.flush()
    room_image = RoomImage(
        session_id=design_session.id, original_path="x", file_hash=f"h-{class_label}-{confidence}",
        width=800, height=600,
    )
    db.add(room_image)
    db.flush()
    analysis = RoomAnalysis(
        image_id=room_image.id, room_width_cm=room_width_cm, room_length_cm=room_length_cm,
        scale_source=ScaleSource.USER_PROVIDED, model_versions={"source": "real_upload"},
    )
    db.add(analysis)
    db.flush()
    detected = DetectedObject(
        analysis_id=analysis.id, class_label=class_label, confidence=confidence,
        source=DetectionSource.REAL_DETECTION, bbox={"x": 0, "y": 0, "w": 10, "h": 10}, area_px=100,
    )
    db.add(detected)
    db.commit()
    return analysis, detected


# --- Unit-level: confirm_detected_object_geometry + load_room_model_from_db ---

def test_confirming_rejects_wrong_source(app):
    with Session(get_engine()) as db:
        analysis, detected = _make_analysis_with_detection(db)
        detected.source = DetectionSource.REAL_SEGMENTATION
        db.commit()
        with pytest.raises(UnconfirmableDetectionError):
            confirm_detected_object_geometry(
                db, detected, width_cm=80, depth_cm=80, height_cm=80, x_cm=100, y_cm=100, rotation_deg=0
            )


def test_confirming_rejects_unmapped_class(app):
    with Session(get_engine()) as db:
        analysis, detected = _make_analysis_with_detection(db, class_label="tv")
        with pytest.raises(UnconfirmableDetectionError):
            confirm_detected_object_geometry(
                db, detected, width_cm=80, depth_cm=80, height_cm=80, x_cm=100, y_cm=100, rotation_deg=0
            )


def test_confirming_rejects_low_confidence(app):
    with Session(get_engine()) as db:
        analysis, detected = _make_analysis_with_detection(db, confidence=0.1)
        with pytest.raises(UnconfirmableDetectionError):
            confirm_detected_object_geometry(
                db, detected, width_cm=80, depth_cm=80, height_cm=80, x_cm=100, y_cm=100, rotation_deg=0
            )


def test_confirmed_geometry_becomes_a_real_existing_furniture_item(app):
    with Session(get_engine()) as db:
        analysis, detected = _make_analysis_with_detection(db, class_label="couch", confidence=0.9)
        confirm_detected_object_geometry(
            db, detected, width_cm=200, depth_cm=90, height_cm=85, x_cm=150, y_cm=200, rotation_deg=90
        )
        loaded: LoadedAnalysis = load_room_model_from_db(db, analysis, "living_room")
    assert len(loaded.room.existing_furniture) == 1
    item = loaded.room.existing_furniture[0]
    assert item.label == "couch"
    assert item.is_existing is True
    assert item.category == "sofa"
    assert (item.width_cm, item.depth_cm, item.height_cm) == (200, 90, 85)
    assert (item.x_cm, item.y_cm, item.rotation_deg) == (150, 200, 90)


def test_confirming_excludes_the_item_from_the_area_only_reservation(app):
    """Before confirming, the couch reduces free_space_ratio via the
    area-only reservation; after confirming, it's precisely accounted for
    as a real placed object instead, so the reservation must drop back to
    the unset (None -> DEFAULT_FREE_SPACE_RATIO) baseline rather than
    double-counting the same couch twice."""
    with Session(get_engine()) as db:
        analysis, detected = _make_analysis_with_detection(db, class_label="couch", confidence=0.9)
        from ai.room_analysis.db_adapter import _recompute_free_space_ratio

        _recompute_free_space_ratio(db, analysis)
        db.commit()
        assert analysis.free_space_ratio is not None
        assert analysis.free_space_ratio < DEFAULT_FREE_SPACE_RATIO

        confirm_detected_object_geometry(
            db, detected, width_cm=200, depth_cm=90, height_cm=85, x_cm=150, y_cm=200, rotation_deg=0
        )
        assert analysis.free_space_ratio is None  # back to "no unconfirmed reservation" baseline


# --- API-level: the full real-photo flow through the live app ---

@requires_dataset
def test_confirm_geometry_endpoint_places_a_real_object_in_the_layout(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)

    with open(REAL_PHOTO, "rb") as f:
        photo_bytes = f.read()
    data = {
        "image": (io.BytesIO(photo_bytes), "room.jpg", "image/jpeg"),
        "room_width_cm": "400", "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    job = _poll_job_to_terminal(client, resp.json["style_job_id"])
    assert job["status"] == "done", job

    style = client.get(f"/api/sessions/{session_id}/style").json
    couch = next(item for item in style["detected_objects"]["furniture"] if item["label"] == "couch")
    assert couch["can_confirm_geometry"] is True
    assert couch["confirmed"] is False

    patch_resp = client.patch(
        f"/api/sessions/{session_id}/detected-objects/{couch['id']}/geometry",
        json={"width_cm": 200, "depth_cm": 90, "height_cm": 85, "x_cm": 100, "y_cm": 100, "rotation_deg": 0},
        headers=csrf_headers(),
    )
    assert patch_resp.status_code == 200, patch_resp.json
    assert patch_resp.json["detected_object"]["confirmed"] is True

    client.patch(
        f"/api/sessions/{session_id}", json={"preferred_style": "Modern", "budget": 80000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    gen_job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    assert gen_job["status"] == "done", gen_job

    layout = client.get(f"/api/sessions/{session_id}/layout").json["layout"]
    existing = [obj for obj in layout["objects"] if obj["is_existing"]]
    assert len(existing) == 1
    assert existing[0]["label"] == "couch"
    assert existing[0]["width_cm"] == 200
    assert existing[0]["depth_cm"] == 90


@requires_dataset
def test_confirm_geometry_rejects_out_of_bounds_position(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    with open(REAL_PHOTO, "rb") as f:
        photo_bytes = f.read()
    data = {
        "image": (io.BytesIO(photo_bytes), "room.jpg", "image/jpeg"),
        "room_width_cm": "400", "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    job = _poll_job_to_terminal(client, resp.json["style_job_id"])
    assert job["status"] == "done", job
    style = client.get(f"/api/sessions/{session_id}/style").json
    couch = next(item for item in style["detected_objects"]["furniture"] if item["label"] == "couch")

    # A 200x90 footprint centered at (390, 100) sticks 90cm out past the
    # 400cm-wide room's edge.
    resp = client.patch(
        f"/api/sessions/{session_id}/detected-objects/{couch['id']}/geometry",
        json={"width_cm": 200, "depth_cm": 90, "height_cm": 85, "x_cm": 390, "y_cm": 100, "rotation_deg": 0},
        headers=csrf_headers(),
    )
    assert resp.status_code == 400


@requires_dataset
def test_second_user_cannot_confirm_first_users_detection(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    with open(REAL_PHOTO, "rb") as f:
        photo_bytes = f.read()
    data = {
        "image": (io.BytesIO(photo_bytes), "room.jpg", "image/jpeg"),
        "room_width_cm": "400", "room_length_cm": "500",
    }
    resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    job = _poll_job_to_terminal(client, resp.json["style_job_id"])
    assert job["status"] == "done", job
    style = client.get(f"/api/sessions/{session_id}/style").json
    couch = next(item for item in style["detected_objects"]["furniture"] if item["label"] == "couch")
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    resp = client.patch(
        f"/api/sessions/{session_id}/detected-objects/{couch['id']}/geometry",
        json={"width_cm": 200, "depth_cm": 90, "height_cm": 85, "x_cm": 100, "y_cm": 100, "rotation_deg": 0},
        headers=csrf_headers(),
    )
    assert resp.status_code == 404
