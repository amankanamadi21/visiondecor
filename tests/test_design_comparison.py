"""
FR-9 (design comparison) tests: listing iterations and fetching a SPECIFIC
past iteration's recommendation/layout, not just the latest.
"""
from __future__ import annotations

import io
import time

from ai.room_analysis.sample_rooms import SAMPLES_DIR


def _register_and_login(client, email="alice@example.com", password="hunter2222", name="Alice"):
    client.post("/api/auth/register", json={"email": email, "password": password, "name": name})


def _poll_job_to_terminal(client, job_id, timeout_s=15):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        job = resp.json["job"]
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.1)
    raise TimeoutError(f"job {job_id} did not reach a terminal state within {timeout_s}s")


def _setup_two_iterations(client, csrf_headers):
    """Generates a design, then submits feedback to force a second iteration
    — mirrors exactly how a real user creates multiple iterations to
    compare (see tests/test_feedback_api.py, same pattern).

    Uses the larger living-room fixture (420x520cm) and a budget-only
    feedback ("reduce cost") rather than a style shift: a style change can
    legitimately swap in bulkier catalog items for the same category (e.g.
    Industrial's larger bed) and, in the small bedroom fixture, was
    observed to produce a genuine, deterministic LayoutInfeasibleError —
    real, honest behavior, but not what this test is trying to exercise.
    A budget-only feedback picks a cheaper item within the SAME category
    the first iteration already placed successfully, avoiding that edge
    case while still producing a genuinely different second iteration."""
    session_resp = client.post("/api/sessions", json={"room_type": "living_room"}, headers=csrf_headers())
    session_id = session_resp.json["session"]["id"]

    with open(f"{SAMPLES_DIR}/living_room_modern_cluttered.jpg", "rb") as f:
        sample_bytes = f.read()
    data = {"image": (io.BytesIO(sample_bytes), "living_room_modern_cluttered.jpg", "image/jpeg")}
    upload_resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, upload_resp.json["job_id"])

    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": "Contemporary", "budget": 80000},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    _poll_job_to_terminal(client, gen_resp.json["job_id"])

    fb_resp = client.post(
        f"/api/sessions/{session_id}/feedback",
        json={"raw_text": "reduce cost please"},
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, fb_resp.json["job_id"])
    return session_id


def test_iterations_lists_both_generations_in_order(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_two_iterations(client, csrf_headers)

    resp = client.get(f"/api/sessions/{session_id}/iterations")
    assert resp.status_code == 200
    iterations = resp.json["iterations"]
    assert [it["iteration"] for it in iterations] == [1, 2]
    assert all(it["layout_score"] is not None for it in iterations)
    assert all(it["item_count"] > 0 for it in iterations)


def test_can_fetch_a_specific_past_iteration_not_just_latest(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_two_iterations(client, csrf_headers)

    first = client.get(f"/api/sessions/{session_id}/recommendation?iteration=1").json["recommendation"]
    latest = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    assert first["iteration"] == 1
    assert latest["iteration"] == 2
    # The two iterations must genuinely be distinct rows, not the same data
    # returned twice — budget_delta from "reduce cost" (feedback_service.py's
    # fixed -15% heuristic) is the reliable, deterministic signal here,
    # rather than asserting the item set changed (a cost cut may or may not
    # be enough to displace an already-cheap item, so that isn't guaranteed).
    assert latest["budget"] < first["budget"]
    assert first["budget"] == 80000.0
    assert latest["budget"] == round(80000.0 * 0.85, 2)

    first_layout = client.get(f"/api/sessions/{session_id}/layout?iteration=1").json["layout"]
    assert all(first_layout["constraints_satisfied"].values())


def test_iteration_query_param_ignored_when_it_does_not_exist(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_two_iterations(client, csrf_headers)
    resp = client.get(f"/api/sessions/{session_id}/recommendation?iteration=999")
    assert resp.status_code == 404


def test_second_user_cannot_list_first_users_iterations(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _setup_two_iterations(client, csrf_headers)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    assert client.get(f"/api/sessions/{session_id}/iterations").status_code == 404
