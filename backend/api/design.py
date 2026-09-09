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

import os

from flask import Blueprint, current_app, g, jsonify, request, send_file

from sqlalchemy import select

from backend.api.sessions import get_owned_session
from backend.db import get_session
from backend.errors import not_found, validation_error
from backend.models.layout import Layout, LayoutObject
from backend.models.recommendation import Recommendation, RecommendationItem
from ai.room_analysis.db_adapter import (
    DETECTION_TO_CATALOG_CATEGORY,
    RESERVATION_CONFIDENCE_THRESHOLD,
    UnconfirmableDetectionError,
    confirm_detected_object_geometry,
)
from backend.models.room import DetectedObject, DetectionSource, RoomAnalysis, RoomImage
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


FURNITURE_SOURCES = (DetectionSource.DETECTION, DetectionSource.REAL_DETECTION)
ARCHITECTURAL_SOURCES = (DetectionSource.SEGMENTATION, DetectionSource.REAL_SEGMENTATION)


def _furniture_dict(obj: DetectedObject) -> dict:
    can_confirm = (
        obj.source == DetectionSource.REAL_DETECTION
        and obj.class_label in DETECTION_TO_CATALOG_CATEGORY
        and obj.confidence >= RESERVATION_CONFIDENCE_THRESHOLD
    )
    return {
        "id": obj.id,
        "label": obj.class_label,
        "confidence": obj.confidence,
        "can_confirm_geometry": can_confirm,
        "confirmed": obj.confirmed_width_cm is not None,
        "confirmed_geometry": (
            {
                "width_cm": obj.confirmed_width_cm, "depth_cm": obj.confirmed_depth_cm,
                "height_cm": obj.confirmed_height_cm, "x_cm": obj.confirmed_x_cm,
                "y_cm": obj.confirmed_y_cm, "rotation_deg": obj.confirmed_rotation_deg,
            }
            if obj.confirmed_width_cm is not None
            else None
        ),
    }


def _detected_objects_dict(analysis: RoomAnalysis, is_sample_room: bool) -> dict:
    """Display-only summary of what FR-2's room analysis found — real CV
    output (2026-09-08 batch) for a genuine photo, or the fixture's labeled
    ground truth for a sample room (both already exist as DetectedObject
    rows; this just presents them uniformly). Confidence is always real:
    1.0 for fixture ground truth, the actual model output for real CV.
    `can_confirm_geometry` (2026-09-08) tells the frontend which furniture
    entries can go through confirm_detected_object_geometry — real,
    confident detections of a class with a catalog-category match."""
    furniture = [_furniture_dict(obj) for obj in analysis.detected_objects if obj.source in FURNITURE_SOURCES]
    architectural = [
        {"label": obj.class_label, "confidence": obj.confidence}
        for obj in analysis.detected_objects
        if obj.source in ARCHITECTURAL_SOURCES
    ]
    return {
        "source": "fixture_ground_truth" if is_sample_room else "real_cv",
        "furniture": furniture,
        "architectural": architectural,
    }


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
    is_sample_room = _session_used_sample_room(db, session_id)
    return jsonify(
        {
            "style": {
                "predicted_style": prediction.predicted_style,
                "confidence": prediction.confidence,
                "alternatives": prediction.alternatives,
                "abstained": prediction.abstained,
                "model_name": prediction.model_name,
            },
            "is_sample_room": is_sample_room,
            "has_known_dimensions": analysis.room_width_cm is not None and analysis.room_length_cm is not None,
            "room_width_cm": analysis.room_width_cm,
            "room_length_cm": analysis.room_length_cm,
            "detected_objects": _detected_objects_dict(analysis, is_sample_room),
            "original_photo_url": _original_photo_url(analysis, session_id, is_sample_room),
        }
    )


def _original_photo_url(analysis: RoomAnalysis, session_id: int, is_sample_room: bool) -> str | None:
    """2026-09-09: lets the UI show the uploaded photo alongside the
    generated visualization. A sample room's "original" is the shipped
    static demo image (already public at /samples/<name>.jpg, matching
    NewDesignPage's SAMPLE_ROOMS list) — never a real upload — while a real
    photo is served through the authenticated original-photo endpoint."""
    if is_sample_room:
        fixture_name = analysis.model_versions.get("fixture_name") if analysis.model_versions else None
        return f"/samples/{fixture_name}.jpg" if fixture_name else None
    return f"/api/sessions/{session_id}/original-photo"


@bp.get("/<int:session_id>/original-photo")
@login_required
def get_original_photo(session_id: int):
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    # Looked up directly from RoomImage, not via _get_latest_analysis — the
    # photo itself exists immediately on upload, before the style/CV
    # analysis job has necessarily finished (or even started).
    room_image = (
        db.query(RoomImage)
        .filter_by(session_id=session_id)
        .order_by(RoomImage.created_at.desc())
        .first()
    )
    if room_image is None or room_image.original_path.startswith("FIXTURE:"):
        raise not_found("No uploaded photo is available for this design.")
    # os.path.abspath: same fix as get_visualization_image (2026-09-09) —
    # send_file resolves a relative path against app.root_path, not cwd.
    return send_file(os.path.abspath(room_image.original_path), mimetype="image/jpeg")


# Sanity bounds — the same kind used for room dimensions (D004): catch a
# unit mistake (e.g. meters typed where cm was expected), not a real
# furniture-size limit.
MIN_ITEM_DIMENSION_CM = 5.0
MAX_ITEM_DIMENSION_CM = 400.0


@bp.patch("/<int:session_id>/detected-objects/<int:detected_object_id>/geometry")
@login_required
def confirm_detected_object(session_id: int, detected_object_id: int):
    """2026-09-08: "optional, from the results page" decision — lets the
    user confirm a confident real detection's actual width/depth/height and
    where it sits in the room, turning it into a genuinely positioned
    existing object (see ai/room_analysis/db_adapter.py's
    confirm_detected_object_geometry for why every number here must be
    user-provided, never derived from the pixel bbox alone)."""
    db = get_session()
    get_owned_session(db, session_id, g.user.id)

    analysis = _get_latest_analysis(db, session_id)
    detected_object = db.get(DetectedObject, detected_object_id)
    if (
        analysis is None
        or detected_object is None
        or detected_object.analysis_id != analysis.id
    ):
        raise not_found("No such detected object for this design.")
    if analysis.room_width_cm is None or analysis.room_length_cm is None:
        raise validation_error("This design has no known room dimensions to place an item within.")

    data = request.get_json(silent=True) or {}
    required_fields = ("width_cm", "depth_cm", "height_cm", "x_cm", "y_cm")
    for field in required_fields:
        if not isinstance(data.get(field), (int, float)):
            raise validation_error(f"{field} is required and must be a number.", {"field": field})

    width_cm, depth_cm, height_cm = data["width_cm"], data["depth_cm"], data["height_cm"]
    for field, value in (("width_cm", width_cm), ("depth_cm", depth_cm), ("height_cm", height_cm)):
        if not (MIN_ITEM_DIMENSION_CM <= value <= MAX_ITEM_DIMENSION_CM):
            raise validation_error(
                f"{field} must be between {MIN_ITEM_DIMENSION_CM:.0f} and {MAX_ITEM_DIMENSION_CM:.0f} cm.",
                {"field": field},
            )

    rotation_deg = data.get("rotation_deg", 0)
    if rotation_deg not in (0, 90, 180, 270):
        raise validation_error("rotation_deg must be one of 0, 90, 180, 270.", {"field": "rotation_deg"})

    x_cm, y_cm = data["x_cm"], data["y_cm"]
    footprint_w, footprint_d = (depth_cm, width_cm) if rotation_deg in (90, 270) else (width_cm, depth_cm)
    if not (0 <= x_cm - footprint_w / 2 and x_cm + footprint_w / 2 <= analysis.room_width_cm):
        raise validation_error("This item's footprint doesn't fit within the room's width at that position.", {"field": "x_cm"})
    if not (0 <= y_cm - footprint_d / 2 and y_cm + footprint_d / 2 <= analysis.room_length_cm):
        raise validation_error("This item's footprint doesn't fit within the room's length at that position.", {"field": "y_cm"})

    try:
        confirm_detected_object_geometry(
            db, detected_object, width_cm=width_cm, depth_cm=depth_cm, height_cm=height_cm,
            x_cm=x_cm, y_cm=y_cm, rotation_deg=rotation_deg,
        )
    except UnconfirmableDetectionError as exc:
        raise validation_error(str(exc))

    return jsonify({"detected_object": _furniture_dict(detected_object)})


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
            "product_url": c.product_url,
            "price_verified_at": c.price_verified_at.isoformat() if c.price_verified_at else None,
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
    # image_path is stored relative to the process's cwd at generation time
    # (see pipeline_stages.py's GENERATED_DIR handling) — but Flask's
    # send_file resolves a relative path against app.root_path (backend/),
    # not cwd (the repo root, per this project's documented run command),
    # which silently 404s whenever they differ. os.path.abspath resolves
    # against os.getcwd() instead, matching how the path was originally
    # constructed. Found live: every prior manual verification this session
    # happened to run Flask from backend/, which made root_path == cwd and
    # masked this exact mismatch.
    return send_file(os.path.abspath(visualization.image_path), mimetype="image/jpeg")


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
