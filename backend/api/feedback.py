"""
Feedback routes (FR-7, decision D024). Submitting feedback: parses the raw
text into structured deltas, applies style/budget shifts directly to the
session, stores the Feedback row (which the next `generate` job reads to
honor keep/remove/crowding — see pipeline_stages.run_generate_design), and
immediately kicks off that regeneration job so the user sees a refined
design without a separate manual step.

This is preference-state updating, not model retraining or fine-tuning
(restates R-11 — brief PART 10's "continuous improvement" is this session-
scoped preference adjustment, never any change to a trained model or its
weights).
"""
from __future__ import annotations

import os

from flask import Blueprint, current_app, g, jsonify, request

from backend.api.sessions import get_owned_session
from backend.db import get_session
from backend.errors import validation_error
from backend.models.feedback import Feedback
from backend.models.recommendation import Recommendation
from backend.models.session import JobStage
from backend.services.feedback_service import parse_feedback
from backend.utils.auth_decorators import login_required

bp = Blueprint("feedback", __name__, url_prefix="/api/sessions")


def _recommendation_items_for_parsing(rec: Recommendation) -> list[dict]:
    return [
        {
            "catalog_item": {
                "id": item.catalog_item.id,
                "name": item.catalog_item.name,
                "category": item.catalog_item.category,
            }
        }
        for item in rec.items
    ]


@bp.post("/<int:session_id>/feedback")
@login_required
def submit_feedback(session_id: int):
    db = get_session()
    design_session = get_owned_session(db, session_id, g.user.id)

    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    rating = data.get("rating")
    if not raw_text:
        raise validation_error("Please provide feedback text.", {"field": "raw_text"})
    if rating is not None and (not isinstance(rating, int) or not (1 <= rating <= 5)):
        raise validation_error("rating must be an integer from 1 to 5.", {"field": "rating"})

    latest_rec = (
        db.query(Recommendation)
        .filter_by(session_id=session_id)
        .order_by(Recommendation.iteration.desc())
        .first()
    )
    current_items = _recommendation_items_for_parsing(latest_rec) if latest_rec else []
    current_budget = float(design_session.budget) if design_session.budget else 0.0

    gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
    deltas = parse_feedback(raw_text, current_items, current_budget, gemini_api_key=gemini_key)

    # Apply session-level shifts immediately (D024) — keep/remove/crowding
    # deltas are applied later, inside the next generate job, since they
    # affect recommendation selection rather than session preferences.
    if deltas.get("style_shift"):
        design_session.preferred_style = deltas["style_shift"]
    if deltas.get("budget_delta") and design_session.budget is not None:
        design_session.budget = max(0.0, float(design_session.budget) + deltas["budget_delta"])

    feedback = Feedback(
        session_id=session_id,
        recommendation_id=latest_rec.id if latest_rec else None,
        raw_text=raw_text,
        structured_deltas=deltas,
        rating=rating,
    )
    db.add(feedback)
    db.commit()

    job_runner = current_app.config["VD_JOB_RUNNER"]

    def _work(job_id: int, report_progress):
        from backend.db import get_engine
        from backend.services.pipeline_stages import run_generate_design
        from sqlalchemy.orm import Session as SASession

        run_generate_design(
            job_id, report_progress, session_id=session_id,
            session_factory=lambda: SASession(get_engine()),
        )

    job_id = job_runner.submit(session_id, JobStage.GENERATE_DESIGN, _work)

    return (
        jsonify(
            {
                "feedback": {
                    "id": feedback.id,
                    "raw_text": feedback.raw_text,
                    "structured_deltas": feedback.structured_deltas,
                    "rating": feedback.rating,
                },
                "job_id": job_id,
            }
        ),
        202,
    )


@bp.get("/<int:session_id>/feedback")
@login_required
def list_feedback(session_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    entries = (
        db.query(Feedback)
        .filter_by(session_id=session_id)
        .order_by(Feedback.created_at.desc())
        .all()
    )
    return jsonify(
        {
            "feedback": [
                {
                    "id": f.id,
                    "raw_text": f.raw_text,
                    "structured_deltas": f.structured_deltas,
                    "rating": f.rating,
                    "created_at": f.created_at.isoformat(),
                }
                for f in entries
            ]
        }
    )
