"""
Real furniture detection (ai.room_analysis.detection, pretrained COCO
YOLOv8n) + architectural segmentation (ai.room_analysis.segmentation,
pretrained ADE20K SegFormer-B0) — 2026-09-08 CV batch, FR-2/Report Issue
R-07.

Two scope decisions apply, both locked with the user:
1. Detect & DISPLAY — real detections are persisted and shown to the user.
2. "Area-only reservation" (amending the original display-only-only scope
   once detection quality had actually been measured): confidently-detected
   furniture with a class mapped to a real catalog category reduces the
   room's free_space_ratio, using the catalog's own mean footprint for that
   category. A detection is NEVER given a real (x, y) position or exact size
   from the pixel bbox alone — a single 2D photo has no depth information to
   derive one honestly — so by default the layout's existing-furniture set
   stays empty. The tests at the bottom guard exactly that boundary.
   (tests/test_confirm_geometry.py covers the one exception: a user can
   explicitly CONFIRM real geometry for a detection, which then does become
   a positioned existing object — see ai/room_analysis/db_adapter.py's
   confirm_detected_object_geometry.)

Unit-level checks run against a real photo from the already-downloaded Houzz
dataset (datasets/houzz_styles/) — a synthetic solid-color image only proves
a detector doesn't crash, not that it actually works.
"""
from __future__ import annotations

import io
import os
import time

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from ai.recommendation.scoring import DEFAULT_FREE_SPACE_RATIO
from ai.room_analysis.db_adapter import MIN_FREE_SPACE_RATIO, _estimate_reserved_area_cm2, _mean_catalog_footprint_cm2
from ai.room_analysis.detection import Detection, detect_objects
from ai.room_analysis.segmentation import segment_architecture
from backend.db import get_engine

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


# --- Unit-level: the detection/segmentation functions themselves ---

@requires_dataset
def test_detect_objects_finds_furniture_in_a_real_photo():
    detections = detect_objects(REAL_PHOTO)
    labels = {d.class_label for d in detections}
    assert "couch" in labels
    for d in detections:
        assert 0.0 <= d.confidence <= 1.0
        assert d.bbox_px["w"] > 0 and d.bbox_px["h"] > 0


def test_detect_objects_finds_nothing_alarming_on_a_blank_image(tmp_path):
    path = tmp_path / "blank.jpg"
    Image.new("RGB", (640, 480), (200, 200, 200)).save(path)
    assert detect_objects(str(path)) == []


@requires_dataset
def test_segment_architecture_finds_wall_floor_ceiling_in_a_real_photo():
    regions = segment_architecture(REAL_PHOTO)
    labels = {r.class_label for r in regions}
    assert {"wall", "floor", "ceiling"}.issubset(labels)
    for r in regions:
        assert 0.0 <= r.confidence <= 1.0
        assert r.area_px > 0
        assert len(r.polygon_px) >= 3  # a real polygon, not a degenerate point/line


def test_label_map_matches_the_installed_models_real_id2label():
    """Regression guard: if a future checkpoint swap changes wording, the
    substring matching in _map_label must still find every architectural
    class among the model's OWN labels — fails loudly instead of silently
    segmenting nothing."""
    from ai.room_analysis.segmentation import _load_model, _map_label

    _, model = _load_model()
    mapped = {_map_label(name) for name in model.config.id2label.values()}
    mapped.discard(None)
    assert {"wall", "floor", "ceiling", "window", "door"}.issubset(mapped)


# --- Integration: wired into the real upload pipeline ---

@requires_dataset
def test_genuine_upload_persists_real_detections_for_display(client, csrf_headers):
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
    assert resp.status_code == 202
    job = _poll_job_to_terminal(client, resp.json["style_job_id"])
    assert job["status"] == "done", job

    style_resp = client.get(f"/api/sessions/{session_id}/style")
    detected = style_resp.json["detected_objects"]
    assert detected["source"] == "real_cv"
    assert any(item["label"] == "couch" for item in detected["furniture"])
    assert any(item["label"] in ("wall", "floor", "ceiling") for item in detected["architectural"])
    for item in detected["furniture"] + detected["architectural"]:
        assert 0.0 <= item["confidence"] <= 1.0


# --- Unit-level: the "area-only reservation" math itself ---

def test_reservation_uses_real_catalog_data_not_a_guessed_number(app):
    """A fake, controlled detection list (not real model output — that's
    covered by the live tests below) isolates the reservation MATH from
    real-model flakiness, matching this project's established pattern of
    testing pure logic separately from real model behavior."""
    with Session(get_engine()) as db:
        fake_detections = [
            Detection(class_label="couch", confidence=0.9, bbox_px={"x": 0, "y": 0, "w": 10, "h": 10}, area_px=100),
        ]
        reserved = _estimate_reserved_area_cm2(db, fake_detections)
        expected = _mean_catalog_footprint_cm2(db, "sofa")  # couch -> sofa category
    assert expected is not None and expected > 0
    assert reserved == expected


def test_reservation_ignores_low_confidence_and_unmapped_classes(app):
    with Session(get_engine()) as db:
        low_confidence = [
            Detection(class_label="couch", confidence=0.1, bbox_px={"x": 0, "y": 0, "w": 10, "h": 10}, area_px=100),
        ]
        no_mapping = [
            Detection(class_label="tv", confidence=0.9, bbox_px={"x": 0, "y": 0, "w": 10, "h": 10}, area_px=100),
        ]
        assert _estimate_reserved_area_cm2(db, low_confidence) == 0.0
        assert _estimate_reserved_area_cm2(db, no_mapping) == 0.0


# --- Integration: wired into the real upload pipeline ---

@requires_dataset
def test_confident_real_detections_reduce_free_space_but_never_place_an_object(client, csrf_headers):
    """The current, amended boundary (2026-09-08): a real photo with real,
    persisted furniture detections CAN change free_space_ratio (and
    therefore recommendation scoring) via the area-only reservation — but
    must still never be modeled as containing a positioned "existing"
    object in the layout, since a single 2D photo can't honestly measure
    one. If the layout ever gains an is_existing object from this path,
    someone wired REAL_DETECTION into load_room_model_from_db's furniture
    list without that being a separately reviewed decision."""
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

    detected = client.get(f"/api/sessions/{session_id}/style").json["detected_objects"]
    assert any(item["label"] == "couch" for item in detected["furniture"])  # confirms this test photo still detects a mapped class

    with Session(get_engine()) as db:
        from backend.models.room import RoomAnalysis

        analysis = db.query(RoomAnalysis).order_by(RoomAnalysis.id.desc()).first()
        assert analysis.free_space_ratio is not None
        assert MIN_FREE_SPACE_RATIO <= analysis.free_space_ratio < DEFAULT_FREE_SPACE_RATIO

    client.patch(
        f"/api/sessions/{session_id}", json={"preferred_style": "Modern", "budget": 80000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    gen_job = _poll_job_to_terminal(client, gen_resp.json["job_id"])
    assert gen_job["status"] == "done", gen_job

    layout = client.get(f"/api/sessions/{session_id}/layout").json["layout"]
    assert not any(obj["is_existing"] for obj in layout["objects"])
