"""
Feedback API integration tests (FR-7, decision D024): submitting feedback
must apply style/budget shifts, store the structured deltas, and trigger a
NEW recommendation iteration that actually honors keep/remove requests.
"""
from __future__ import annotations

import io
import time

from ai.room_analysis.sample_rooms import SAMPLES_DIR
from backend.services.feedback_service import _significant_words


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


def _setup_generated_session(client, csrf_headers, fixture_filename="bedroom_small_scandinavian", style="Scandinavian", budget=60000):
    session_resp = client.post("/api/sessions", json={"room_type": "bedroom"}, headers=csrf_headers())
    session_id = session_resp.json["session"]["id"]

    with open(f"{SAMPLES_DIR}/{fixture_filename}.jpg", "rb") as f:
        sample_bytes = f.read()
    data = {"image": (io.BytesIO(sample_bytes), f"{fixture_filename}.jpg", "image/jpeg")}
    upload_resp = client.post(
        f"/api/sessions/{session_id}/image", data=data, content_type="multipart/form-data",
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, upload_resp.json["job_id"])

    client.patch(
        f"/api/sessions/{session_id}",
        json={"preferred_style": style, "budget": budget},
        headers=csrf_headers(),
    )
    gen_resp = client.post(f"/api/sessions/{session_id}/generate", headers=csrf_headers())
    _poll_job_to_terminal(client, gen_resp.json["job_id"])
    return session_id


def test_feedback_requires_text(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_generated_session(client, csrf_headers)
    resp = client.post(f"/api/sessions/{session_id}/feedback", json={"raw_text": ""}, headers=csrf_headers())
    assert resp.status_code == 400


def test_feedback_applies_style_shift_and_triggers_new_iteration(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_generated_session(client, csrf_headers, style="Scandinavian")

    resp = client.post(
        f"/api/sessions/{session_id}/feedback",
        json={"raw_text": "I don't like this, make it more industrial"},
        headers=csrf_headers(),
    )
    assert resp.status_code == 202
    assert resp.json["feedback"]["structured_deltas"]["style_shift"] == "Industrial"
    _poll_job_to_terminal(client, resp.json["job_id"])

    session_detail = client.get(f"/api/sessions/{session_id}").json["session"]
    assert session_detail["preferred_style"] == "Industrial"

    rec = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    assert rec["iteration"] == 2  # a genuinely new iteration, not the original


def test_feedback_remove_item_excludes_it_from_next_iteration(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_generated_session(client, csrf_headers, style="Scandinavian", budget=60000)

    rec1 = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    first_item_name = rec1["items"][0]["catalog_item"]["name"]
    # Use the same significant-word extraction the parser itself uses,
    # rather than a naive "last word" guess (which broke once already on a
    # name like "Platform Bed Frame (Queen)" — see feedback_service.py).
    key_word = _significant_words(first_item_name)[0]

    resp = client.post(
        f"/api/sessions/{session_id}/feedback",
        json={"raw_text": f"remove the {key_word}"},
        headers=csrf_headers(),
    )
    _poll_job_to_terminal(client, resp.json["job_id"])

    rec2 = client.get(f"/api/sessions/{session_id}/recommendation").json["recommendation"]
    rec2_names = [i["catalog_item"]["name"] for i in rec2["items"]]
    assert first_item_name not in rec2_names


def test_feedback_history_lists_submitted_entries(client, csrf_headers):
    _register_and_login(client)
    session_id = _setup_generated_session(client, csrf_headers)
    client.post(f"/api/sessions/{session_id}/feedback", json={"raw_text": "reduce cost"}, headers=csrf_headers())

    history = client.get(f"/api/sessions/{session_id}/feedback").json["feedback"]
    assert len(history) == 1
    assert history[0]["raw_text"] == "reduce cost"


def test_second_user_cannot_submit_feedback_on_first_users_session(client, csrf_headers):
    _register_and_login(client, "alice@example.com")
    session_id = _setup_generated_session(client, csrf_headers)
    client.post("/api/auth/logout")

    _register_and_login(client, "bob@example.com", name="Bob")
    resp = client.post(
        f"/api/sessions/{session_id}/feedback", json={"raw_text": "keep it"}, headers=csrf_headers()
    )
    assert resp.status_code == 404
