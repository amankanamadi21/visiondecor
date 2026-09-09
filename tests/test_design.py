"""
Design generation API tests (Batch 2): POST /generate, GET /recommendation,
GET /layout, and the honest failure modes (no analysis yet, incomplete
preferences) rather than a silent fallback to fixture data (decision D018
guardrail).
"""
from __future__ import annotations

import time

from sqlalchemy.orm import Session

from ai.room_analysis.db_adapter import persist_fixture
from ai.room_analysis.fixtures import get_fixture
from backend.db import get_engine


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _create_session(client, csrf_headers, room_type="bedroom"):
    resp = client.post("/api/sessions", json={"room_type": room_type}, headers=csrf_headers())
    return resp.json["session"]["id"]


def _set_preferences(client, csrf_headers, session_id, style="Scandinavian", colors=None, budget=60000):
    return client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": style, "preferred_colors": colors or ["white", "natural wood"], "budget": budget},
        headers=csrf_headers(),
    )


def _attach_fixture(app, session_id, fixture_name="bedroom_small_scandinavian"):
    """Test-only equivalent of scripts/seed_fixture_analysis.py — writes
    real RoomAnalysis/DetectedObject/StylePrediction rows for the session."""
    with app.app_context():
        with Session(get_engine()) as db:
            persist_fixture(db, session_id, get_fixture(fixture_name))


def _poll_job_to_terminal(client, job_id, timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def test_generate_requires_preferences_to_be_set_first(client, app, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    _attach_fixture(app, session_id)
    # Deliberately NOT calling _set_preferences.

    resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    assert resp.status_code == 202
    job = _poll_job_to_terminal(client, resp.json["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == "preferences_incomplete"


def test_generate_requires_room_analysis_to_exist(client, app, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    _set_preferences(client, csrf_headers, session_id)
    # Deliberately NOT attaching any fixture analysis — this is the D018
    # guardrail: no silent fallback to fixture data in the real pipeline.

    resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    job = _poll_job_to_terminal(client, resp.json["job_id"])
    assert job["status"] == "failed"
    assert job["error_code"] == "room_analysis_missing"


def test_full_generate_flow_produces_recommendation_and_layout(client, app, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers, room_type="bedroom")
    _attach_fixture(app, session_id, "bedroom_small_scandinavian")
    _set_preferences(client, csrf_headers, session_id, style="Scandinavian", budget=60000)

    resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    assert resp.status_code == 202
    job = _poll_job_to_terminal(client, resp.json["job_id"])
    assert job["status"] == "done", job

    rec_resp = client.get(f"/api/sessions/{session_id}/recommendation")
    assert rec_resp.status_code == 200
    rec = rec_resp.json["recommendation"]
    assert rec["iteration"] == 1
    assert len(rec["items"]) > 0
    for item in rec["items"]:
        # 2026-09-09: catalog is real product data now (was MOCK) — the
        # invariant is still "never hidden", just pointed the other way:
        # every real row must disclose a real product_url + verified date.
        assert item["catalog_item"]["data_source"] == "REAL"
        assert item["catalog_item"]["product_url"]
        assert item["catalog_item"]["price_verified_at"]

    layout_resp = client.get(f"/api/sessions/{session_id}/layout")
    assert layout_resp.status_code == 200
    layout = layout_resp.json["layout"]
    assert all(layout["constraints_satisfied"].values())
    assert len(layout["objects"]) >= len(rec["items"])  # includes existing furniture too
    assert layout["floorplan_svg"].startswith("<svg")
    assert "Old Sofa" not in layout["floorplan_svg"]  # this fixture has no sofa — regression guard
    assert "Platform Bed Frame" in layout["floorplan_svg"] or any(
        i["catalog_item"]["name"] in layout["floorplan_svg"] for i in rec["items"]
    )


def test_recommendation_not_found_before_generation(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    resp = client.get(f"/api/sessions/{session_id}/recommendation")
    assert resp.status_code == 404


def test_second_user_cannot_trigger_or_read_first_users_design(client, app, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _create_session(client, csrf_headers)
    _attach_fixture(app, session_id)
    _set_preferences(client, csrf_headers, session_id)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    assert client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers()).status_code == 404
    assert client.get(f"/api/sessions/{session_id}/recommendation").status_code == 404
    assert client.get(f"/api/sessions/{session_id}/layout").status_code == 404


def test_preferences_reject_invalid_style(client, csrf_headers):
    _register_and_login(client)
    session_id = _create_session(client, csrf_headers)
    resp = client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Steampunk"},
        headers=csrf_headers(),
    )
    assert resp.status_code == 400
