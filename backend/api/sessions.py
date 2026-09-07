"""
Design session routes — FR-1/FR-8 (a session groups one room's images,
analyses, recommendations, layouts and feedback under one user).

Per-user authorization is enforced explicitly here (`_get_owned_session`)
rather than relying on `login_required` alone: being logged in proves *who*
you are, not that you may access a specific session id — a second user must
never be able to fetch the first user's session by guessing its id.
"""
from __future__ import annotations

from flask import Blueprint, g, jsonify, request

from backend.db import get_session
from backend.errors import not_found, validation_error
from backend.models import DesignSession
from backend.utils.auth_decorators import login_required

bp = Blueprint("sessions", __name__, url_prefix="/api/sessions")

ALLOWED_ROOM_TYPES = {"living_room", "bedroom", "office", "study_room", "other"}
# FR-3 style categories, exactly as named in the report.
ALLOWED_STYLES = {"Modern", "Minimalist", "Contemporary", "Traditional", "Industrial", "Scandinavian"}


def _session_dict(s: DesignSession) -> dict:
    return {
        "id": s.id,
        "room_type": s.room_type,
        "title": s.title,
        "status": s.status.value,
        "preferred_style": s.preferred_style,
        "preferred_colors": s.preferred_colors,
        "budget": float(s.budget) if s.budget is not None else None,
        "currency": s.currency,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def get_owned_session(db, session_id: int, user_id: int) -> DesignSession:
    """Fetch a DesignSession, raising 404 (not 403) if it doesn't belong to
    this user — this avoids confirming to an attacker that the id exists."""
    design_session = db.get(DesignSession, session_id)
    if design_session is None or design_session.user_id != user_id:
        raise not_found("Design session not found.")
    return design_session


@bp.post("")
@login_required
def create_session():
    data = request.get_json(silent=True) or {}
    room_type = data.get("room_type")
    if room_type is not None and room_type not in ALLOWED_ROOM_TYPES:
        raise validation_error(
            f"room_type must be one of {sorted(ALLOWED_ROOM_TYPES)}.", {"field": "room_type"}
        )

    db = get_session()
    design_session = DesignSession(
        user_id=g.user.id, room_type=room_type, title=data.get("title")
    )
    db.add(design_session)
    db.commit()
    return jsonify({"session": _session_dict(design_session)}), 201


@bp.get("")
@login_required
def list_sessions():
    db = get_session()
    sessions = (
        db.query(DesignSession)
        .filter_by(user_id=g.user.id)
        .order_by(DesignSession.updated_at.desc())
        .all()
    )
    return jsonify({"sessions": [_session_dict(s) for s in sessions]})


@bp.get("/<int:session_id>")
@login_required
def get_session_detail(session_id: int):
    db = get_session()
    design_session = get_owned_session(db, session_id, g.user.id)
    return jsonify({"session": _session_dict(design_session)})


@bp.patch("/<int:session_id>")
@login_required
def update_session_preferences(session_id: int):
    """FR-1/FR-4: set this design's preferred style, colors, and budget
    (decision D019 — a single total budget; see PLAN.md). Distinct from
    UserPreference, which only stores remembered defaults across designs."""
    db = get_session()
    design_session = get_owned_session(db, session_id, g.user.id)
    data = request.get_json(silent=True) or {}

    if "preferred_style" in data:
        style = data["preferred_style"]
        if style is not None and style not in ALLOWED_STYLES:
            raise validation_error(f"preferred_style must be one of {sorted(ALLOWED_STYLES)}.", {"field": "preferred_style"})
        design_session.preferred_style = style

    if "preferred_colors" in data:
        colors = data["preferred_colors"]
        if colors is not None and (not isinstance(colors, list) or not all(isinstance(c, str) for c in colors)):
            raise validation_error("preferred_colors must be a list of strings.", {"field": "preferred_colors"})
        design_session.preferred_colors = colors

    if "budget" in data:
        budget = data["budget"]
        if budget is not None and (not isinstance(budget, (int, float)) or budget < 0):
            raise validation_error("budget must be a non-negative number.", {"field": "budget"})
        design_session.budget = budget

    if "currency" in data:
        currency = data["currency"]
        if not isinstance(currency, str) or len(currency) != 3:
            raise validation_error("currency must be a 3-letter code.", {"field": "currency"})
        design_session.currency = currency.upper()

    db.commit()
    return jsonify({"session": _session_dict(design_session)})
