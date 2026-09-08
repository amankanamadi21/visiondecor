"""
Design generation routes (Batch 2): trigger the recommendation + layout
optimisation job for a session, and fetch its latest results.

This endpoint reads whatever RoomAnalysis/StylePrediction rows already
exist for the session — real ones from a future CV pipeline, or dev-only
fixture rows (decision D018, scripts/seed_fixture_analysis.py). It never
falls back to fixture data itself; if no analysis exists, the background
job fails with a specific, honest error (PipelineStageError
"room_analysis_missing"), surfaced through the normal job-polling path.
"""
from __future__ import annotations

from flask import Blueprint, current_app, g, jsonify, request, send_file

from sqlalchemy import select

from backend.api.sessions import get_owned_session
from backend.db import get_session
from backend.errors import not_found
from backend.models.layout import Layout, LayoutObject
from backend.models.recommendation import Recommendation, RecommendationItem
from backend.models.room import RoomAnalysis, RoomImage
from backend.models.session import JobStage
from backend.models.visualization import Visualization
from backend.utils.auth_decorators import login_required

bp = Blueprint("design", __name__, url_prefix="/api/sessions")


def _get_latest_analysis(db, session_id: int) -> RoomAnalysis | None:
    return db.execute(
        select(RoomAnalysis)
        .join(RoomImage, RoomAnalysis.image_id == RoomImage.id)
        .where(RoomImage.session_id == session_id)
        .order_by(RoomAnalysis.created_at.desc())
    ).scalars().first()


def _session_used_sample_room(db, session_id: int) -> bool:
    """D022 disclosure guardrail: true iff the session's latest RoomAnalysis
    came from a recognized sample-room image (persist_fixture stamps
    model_versions.source='fixture'), never true for a genuine user photo."""
    analysis = _get_latest_analysis(db, session_id)
    return bool(analysis and analysis.model_versions and analysis.model_versions.get("source") == "fixture")


@bp.get("/<int:session_id>/style")
@login_required
def get_latest_style(session_id: int):
    """D005/Batch ④ — works for both a recognized sample room (fixture's
    labeled demo style) and a genuine uploaded photo (real CLIP prediction);
    both produce a real StylePrediction row, distinguished only by
    `is_sample_room` for disclosure (D022), never by data shape."""
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    analysis = _get_latest_analysis(db, session_id)
    if analysis is None or not analysis.style_predictions:
        raise not_found("No style prediction is available for this design yet.")

    prediction = analysis.style_predictions[-1]
    return jsonify(
        {
            "style": {
                "predicted_style": prediction.predicted_style,
                "confidence": prediction.confidence,
                "alternatives": prediction.alternatives,
                "abstained": prediction.abstained,
                "model_name": prediction.model_name,
            },
            "is_sample_room": _session_used_sample_room(db, session_id),
            "has_known_dimensions": analysis.room_width_cm is not None and analysis.room_length_cm is not None,
        }
    )


@bp.post("/<int:session_id>/generate")
@login_required
def generate_design(session_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)  # raises 404 if not owned

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
    return jsonify({"job_id": job_id}), 202


def _recommendation_dict(rec: Recommendation) -> dict:
    return {
        "id": rec.id,
        "iteration": rec.iteration,
        "total_cost": float(rec.total_cost),
        "budget": float(rec.budget),
        "within_budget": rec.within_budget,
        "palette": rec.palette,
        "created_at": rec.created_at.isoformat(),
        "items": [_recommendation_item_dict(item) for item in rec.items],
    }


def _recommendation_item_dict(item: RecommendationItem) -> dict:
    c = item.catalog_item
    return {
        "id": item.id,
        "action": item.action.value,
        "score_breakdown": item.score_breakdown,
        "rationale": item.rationale,
        "quantity": item.quantity,
        "catalog_item": {
            "id": c.id,
            "name": c.name,
            "category": c.category,
            "color": c.color,
            "price": float(c.price),
            "currency": c.currency,
            "width_cm": c.width_cm,
            "depth_cm": c.depth_cm,
            "height_cm": c.height_cm,
            "image_url": c.image_url,
            "data_source": c.data_source,
        },
    }


def _layout_dict(layout: Layout) -> dict:
    return {
        "id": layout.id,
        "layout_score": layout.layout_score,
        "score_breakdown": layout.score_breakdown,
        "constraints_satisfied": layout.constraints_satisfied,
        "algorithm": layout.algorithm,
        "iterations": layout.iterations,
        "objects": [_layout_object_dict(o) for o in layout.objects],
    }


def _layout_object_dict(obj: LayoutObject) -> dict:
    return {
        "label": obj.label,
        "x_cm": obj.x_cm,
        "y_cm": obj.y_cm,
        "width_cm": obj.width_cm,
        "depth_cm": obj.depth_cm,
        "rotation_deg": obj.rotation_deg,
        "is_existing": obj.is_existing,
        "catalog_item_id": obj.catalog_item_id,
    }


def _get_recommendation(db, session_id: int, iteration: int | None) -> Recommendation | None:
    """`iteration=None` means latest — the pre-FR-9 behavior every existing
    caller (and test) relies on. An explicit iteration is what FR-9 (design
    comparison) needs: a specific past iteration, not just the newest."""
    query = db.query(Recommendation).filter_by(session_id=session_id)
    if iteration is not None:
        return query.filter_by(iteration=iteration).first()
    return query.order_by(Recommendation.iteration.desc()).first()


@bp.get("/<int:session_id>/iterations")
@login_required
def list_iterations(session_id: int):
    """FR-9 (design comparison): a lightweight summary of every iteration
    this session has produced, for a comparison picker UI — not the full
    recommendation/layout payload, just enough to choose two to compare."""
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    recommendations = (
        db.query(Recommendation)
        .filter_by(session_id=session_id)
        .order_by(Recommendation.iteration.asc())
        .all()
    )
    summaries = []
    for rec in recommendations:
        layout = (
            db.query(Layout)
            .filter_by(recommendation_id=rec.id)
            .order_by(Layout.created_at.desc())
            .first()
        )
        summaries.append(
            {
                "iteration": rec.iteration,
                "created_at": rec.created_at.isoformat(),
                "total_cost": float(rec.total_cost),
                "within_budget": rec.within_budget,
                "layout_score": layout.layout_score if layout else None,
                "item_count": len(rec.items),
            }
        )
    return jsonify({"iterations": summaries})


@bp.get("/<int:session_id>/recommendation")
@login_required
def get_latest_recommendation(session_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    iteration = request.args.get("iteration", type=int)
    rec = _get_recommendation(db, session_id, iteration)
    if rec is None:
        raise not_found("No recommendation has been generated for this design yet.")
    payload = _recommendation_dict(rec)
    payload["is_sample_room"] = _session_used_sample_room(db, session_id)
    return jsonify({"recommendation": payload})


@bp.get("/<int:session_id>/layout")
@login_required
def get_latest_layout(session_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    iteration = request.args.get("iteration", type=int)
    rec = _get_recommendation(db, session_id, iteration)
    layout = None
    if rec is not None:
        layout = (
            db.query(Layout)
            .filter_by(recommendation_id=rec.id)
            .order_by(Layout.created_at.desc())
            .first()
        )
    if layout is None:
        raise not_found("No layout has been generated for this design yet.")
    payload = _layout_dict(layout)
    payload["is_sample_room"] = _session_used_sample_room(db, session_id)
    payload["floorplan_svg"] = _render_floorplan_for_session(db, session_id, layout)

    visualization = (
        db.query(Visualization)
        .filter_by(layout_id=layout.id)
        .order_by(Visualization.created_at.desc())
        .first()
    )
    payload["visualization"] = (
        {
            "id": visualization.id,
            "provider": visualization.provider,
            # D003/D023 disclosure requirement — the UI must be able to tell
            # the user whether this specific image came from genuine image
            # editing (geometry preserved by construction) or not.
            "structure_preserving": visualization.structure_preserving,
            "cache_hit": visualization.cache_hit,
            "image_url": f"/api/sessions/{session_id}/visualization/{visualization.id}/image",
        }
        if visualization is not None
        else None
    )
    return jsonify({"layout": payload})


@bp.get("/<int:session_id>/visualization/<int:visualization_id>/image")
@login_required
def get_visualization_image(session_id: int, visualization_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    visualization = (
        db.query(Visualization)
        .join(Layout, Visualization.layout_id == Layout.id)
        .join(Recommendation, Layout.recommendation_id == Recommendation.id)
        .filter(Visualization.id == visualization_id, Recommendation.session_id == session_id)
        .first()
    )
    if visualization is None:
        raise not_found("Visualization not found.")
    return send_file(visualization.image_path, mimetype="image/jpeg")


def _render_floorplan_for_session(db, session_id: int, layout: Layout) -> str | None:
    """Regenerated on every request rather than stored: it's fully
    deterministic from data already in the DB (unlike the generative image,
    which is expensive/non-deterministic and DOES get persisted — see
    backend.models.visualization.Visualization)."""
    from ai.room_analysis.db_adapter import load_room_model_from_db
    from ai.visualization.floorplan import render_floorplan_svg
    from backend.models.session import DesignSession

    design_session = db.get(DesignSession, session_id)
    analysis = _get_latest_analysis(db, session_id)
    if analysis is None:
        return None
    loaded = load_room_model_from_db(db, analysis, design_session.room_type or "other")
    return render_floorplan_svg(loaded.room, layout.objects, title="Optimized Layout")
