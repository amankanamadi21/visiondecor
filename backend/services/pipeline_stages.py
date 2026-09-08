"""
Registry of pipeline-stage implementations run by JobRunner.

Batch 1 implemented `preprocess`. Batch 2 adds `generate_design`, which runs
the recommendation engine (ai/recommendation) and layout optimiser
(ai/layout_optimization) against whatever RoomAnalysis/StylePrediction rows
already exist for a session — real ones from a future CV pipeline, or
dev-only fixture rows from scripts/seed_fixture_analysis.py (decision
D018). This function does not know or care which; it only requires the
rows to exist, and raises a clear, specific PipelineStageError if they
don't — it never silently substitutes fixture data (see PLAN.md D018
guardrail).

Batch ④ adds `run_style_recognition_for_upload`: for a genuine (non-sample)
uploaded photo, runs the REAL CLIP-RN50 zero-shot classifier (D005) and
persists a real StylePrediction — attached to a minimal RoomAnalysis "shell"
with dimensions explicitly NULL (`scale_source=UNKNOWN`), since detection/
segmentation/dimension estimation remain deferred (D018/D022, and D004 is
still unresolved). This deliberately does NOT unlock full recommendation
generation for real photos — `run_generate_design` below now raises a
distinct `room_dimensions_missing` error for exactly this case, rather than
crashing on `None * None` or silently guessing a room size.

`room_analysis` (detection/segmentation) and `visualization` remain
deliberate placeholders — there is no fake YOLO detection and no fake
render hiding behind these functions.
"""
from __future__ import annotations

import os
from typing import Callable

from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_DIMENSION_PX = 1600  # long-edge cap; keeps CPU-bound downstream stages fast


class PipelineStageError(Exception):
    """Carries a specific, user-safe error code/message through JobRunner —
    see backend/services/job_runner.py, which uses these instead of its
    generic fallback message when a stage raises this (brief PART 15: every
    failure needs a meaningful message, not a generic 500)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def run_preprocess(job_id: int, report_progress: Callable[[int], None], *, image_path: str, output_path: str) -> None:
    report_progress(10)
    img = Image.open(image_path)
    img.load()
    report_progress(40)

    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    width, height = img.size
    longest = max(width, height)
    if longest > MAX_DIMENSION_PX:
        scale = MAX_DIMENSION_PX / longest
        img = img.resize((int(width * scale), int(height * scale)), Image.LANCZOS)
    report_progress(75)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    img.save(output_path, format="JPEG", quality=90)
    report_progress(100)


def run_style_recognition_for_upload(
    job_id: int,
    report_progress: Callable[[int], None],
    *,
    room_image_id: int,
    image_path: str,
    session_factory,
    room_width_cm: float | None = None,
    room_length_cm: float | None = None,
) -> None:
    """D005, wired into the live upload path for a genuine (non-sample)
    photo — see module docstring. Idempotent: does nothing if this
    RoomImage already has an analysis (e.g. a duplicate upload).

    `room_width_cm`/`room_length_cm` resolve D004 (decision log, 2026-09-08):
    when both are given (validated upstream in backend/api/uploads.py), the
    RoomAnalysis is stamped `scale_source=USER_PROVIDED` with real
    dimensions, unlocking full recommendation generation for a real photo —
    not just a style prediction. When absent, dimensions stay NULL and
    `scale_source=UNKNOWN`, exactly as before this decision was made."""
    from ai.style_recognition.classifier import classify_style
    from backend.models.room import RoomAnalysis, RoomImage, ScaleSource
    from backend.models.style import StylePrediction

    db: Session = session_factory()
    try:
        room_image = db.get(RoomImage, room_image_id)
        if room_image is None or room_image.analyses:
            report_progress(100)
            return

        report_progress(20)
        image = Image.open(image_path)
        result = classify_style(image)
        report_progress(70)

        has_dimensions = room_width_cm is not None and room_length_cm is not None
        analysis = RoomAnalysis(
            image_id=room_image.id,
            floor_polygon=None,
            free_space_ratio=None,
            room_width_cm=room_width_cm,
            room_length_cm=room_length_cm,
            scale_source=ScaleSource.USER_PROVIDED if has_dimensions else ScaleSource.UNKNOWN,
            model_versions={"source": "real_upload", "classifier": result.model_name},
        )
        db.add(analysis)
        db.flush()

        db.add(
            StylePrediction(
                analysis_id=analysis.id,
                predicted_style=result.predicted_style,
                confidence=result.confidence,
                alternatives=result.alternatives,
                model_name=result.model_name,
                abstained=result.abstained,
            )
        )
        db.commit()
        report_progress(100)
    finally:
        db.close()


def run_generate_design(job_id: int, report_progress: Callable[[int], None], *, session_id: int, session_factory) -> None:
    from ai.layout_optimization.optimizer import LayoutInfeasibleError, PlacementSpec, optimize_layout
    from ai.recommendation.scoring import generate_recommendation
    from ai.room_analysis.db_adapter import load_room_model_from_db
    from backend.models.layout import Layout, LayoutObject
    from backend.models.recommendation import Recommendation, RecommendationAction, RecommendationItem
    from backend.models.room import RoomAnalysis, RoomImage
    from backend.models.session import DesignSession, SessionStatus

    db: Session = session_factory()
    try:
        design_session = db.get(DesignSession, session_id)
        if design_session is None:
            raise PipelineStageError("session_not_found", "This design session no longer exists.")

        if design_session.budget is None or not design_session.preferred_style:
            raise PipelineStageError(
                "preferences_incomplete",
                "Please set a preferred style and budget for this design before generating recommendations.",
            )

        analysis = db.execute(
            select(RoomAnalysis)
            .join(RoomImage, RoomAnalysis.image_id == RoomImage.id)
            .where(RoomImage.session_id == session_id)
            .order_by(RoomAnalysis.created_at.desc())
        ).scalars().first()
        if analysis is None:
            raise PipelineStageError(
                "room_analysis_missing",
                "Room analysis is not available yet for this design. Upload a room image and wait for "
                "analysis to complete before generating recommendations.",
            )
        if analysis.room_width_cm is None or analysis.room_length_cm is None:
            # D005/Batch ④: a real (non-sample) uploaded photo gets a genuine
            # style prediction but no known dimensions (D004 remains
            # unresolved — no detection/segmentation/depth estimation yet).
            # Distinct from room_analysis_missing: analysis DOES exist here,
            # it's just incomplete — a different, equally honest failure mode.
            raise PipelineStageError(
                "room_dimensions_missing",
                "This design's room style has been identified, but its physical dimensions are not known "
                "yet, so a layout cannot be generated. Automatic room-dimension detection from a photo is "
                "not yet implemented — try one of the sample rooms to see the full pipeline.",
            )
        report_progress(10)

        loaded = load_room_model_from_db(db, analysis, design_session.room_type or "other")

        # D024 feedback loop: honor deltas from the most recent feedback
        # (if any) — first-iteration generation simply has none.
        from backend.models.feedback import Feedback

        latest_feedback = (
            db.query(Feedback)
            .filter_by(session_id=session_id)
            .order_by(Feedback.created_at.desc())
            .first()
        )
        excluded_ids, forced_keep_ids, drop_categories = [], [], 0
        if latest_feedback is not None and latest_feedback.structured_deltas:
            deltas = latest_feedback.structured_deltas
            excluded_ids = deltas.get("remove_item_ids") or []
            forced_keep_ids = deltas.get("keep_item_ids") or []
            drop_categories = 1 if deltas.get("crowding_shift") == "less" else 0

        rec_result = generate_recommendation(
            db,
            room=loaded.room,
            detected_style=loaded.predicted_style,
            preferred_style=design_session.preferred_style,
            preferred_colors=design_session.preferred_colors or [],
            budget=float(design_session.budget),
            currency=design_session.currency,
            excluded_catalog_ids=excluded_ids,
            forced_keep_ids=forced_keep_ids,
            drop_lowest_priority_categories=drop_categories,
        )
        report_progress(45)

        prior_iterations = db.query(Recommendation).filter_by(session_id=session_id).count()
        recommendation = Recommendation(
            session_id=session_id,
            iteration=prior_iterations + 1,
            total_cost=rec_result.total_cost,
            budget=rec_result.budget,
            within_budget=rec_result.within_budget,
            palette=rec_result.palette,
        )
        db.add(recommendation)
        db.flush()

        for scored in rec_result.items:
            db.add(
                RecommendationItem(
                    recommendation_id=recommendation.id,
                    catalog_item_id=scored.catalog_item.id,
                    action=RecommendationAction.KEEP if scored.action == "keep" else RecommendationAction.ADD,
                    score_breakdown=scored.score_breakdown,
                    rationale=scored.rationale,
                    quantity=1,
                )
            )
        db.commit()
        report_progress(55)

        specs = [
            PlacementSpec(
                label=scored.catalog_item.name, width_cm=scored.catalog_item.width_cm,
                depth_cm=scored.catalog_item.depth_cm, height_cm=scored.catalog_item.height_cm,
                category=scored.category, catalog_item_id=scored.catalog_item.id,
            )
            for scored in rec_result.items
        ]

        try:
            layout_result = optimize_layout(loaded.room, specs)
        except LayoutInfeasibleError as exc:
            raise PipelineStageError("layout_infeasible", str(exc)) from exc
        report_progress(85)

        layout = Layout(
            recommendation_id=recommendation.id,
            layout_score=layout_result.score.total_score,
            score_breakdown=layout_result.score.breakdown,
            constraints_satisfied=layout_result.constraints_satisfied,
            algorithm=layout_result.algorithm,
            iterations=layout_result.iterations_run,
        )
        db.add(layout)
        db.flush()

        for item in loaded.room.existing_furniture:
            db.add(
                LayoutObject(
                    layout_id=layout.id, catalog_item_id=None, label=item.label,
                    x_cm=item.x_cm, y_cm=item.y_cm, width_cm=item.width_cm, depth_cm=item.depth_cm,
                    rotation_deg=item.rotation_deg, is_existing=True,
                )
            )
        for item in layout_result.placed_items:
            db.add(
                LayoutObject(
                    layout_id=layout.id, catalog_item_id=item.catalog_item_id, label=item.label,
                    x_cm=item.x_cm, y_cm=item.y_cm, width_cm=item.width_cm, depth_cm=item.depth_cm,
                    rotation_deg=item.rotation_deg, is_existing=False,
                )
            )

        design_session.status = SessionStatus.READY
        db.commit()
        report_progress(90)

        _attempt_visualization(db, layout, analysis, loaded, rec_result, design_session, layout_result)
        report_progress(100)
    finally:
        db.close()


def _attempt_visualization(db, layout, analysis, loaded, rec_result, design_session, layout_result) -> None:
    """Best-effort — a missing/failed provider is a normal, expected state
    (no GEMINI_API_KEY configured is the documented default), not a job
    failure. The floor plan (always available, computed on demand by the
    layout API) is what guarantees a visual result regardless of what
    happens here."""
    import os

    from ai.visualization.cache import RenderCache
    from ai.visualization.prompt_builder import build_edit_prompt
    from ai.visualization.render_service import build_default_providers, render_with_fallback
    from backend.models.visualization import Visualization

    original_path = analysis.image.original_path
    if original_path.startswith("FIXTURE:") or not os.path.exists(original_path):
        return  # dev-script-only fixture (scripts/seed_fixture_analysis.py) — no real photo bytes to edit

    providers = build_default_providers(
        os.environ.get("GEMINI_API_KEY", "").strip() or None,
        os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip() or None,
        os.environ.get("CLOUDFLARE_API_TOKEN", "").strip() or None,
    )
    if not providers:
        return  # no provider configured — expected default state, not an error

    all_items = [*loaded.room.existing_furniture, *layout_result.placed_items]
    prompt = build_edit_prompt(
        loaded.room, all_items, style=design_session.preferred_style, palette=rec_result.palette
    )

    with open(original_path, "rb") as f:
        room_photo_bytes = f.read()

    generated_dir = os.environ.get("GENERATED_DIR", "./generated")
    cache = RenderCache(os.path.join(generated_dir, "render_cache"))
    result = render_with_fallback(room_photo_bytes, prompt, providers, cache)
    if result is None:
        return  # every configured provider failed — logged in render_service, not fatal here

    image_dir = os.path.join(generated_dir, str(design_session.user_id), str(design_session.id))
    os.makedirs(image_dir, exist_ok=True)
    image_path = os.path.join(image_dir, f"layout_{layout.id}.jpg")
    with open(image_path, "wb") as f:
        f.write(result.image_bytes)

    db.add(
        Visualization(
            layout_id=layout.id, provider=result.provider_name, image_path=image_path,
            prompt_used=prompt, structure_preserving=result.structure_preserving,
            cache_hit=result.cache_hit,
        )
    )
    db.commit()


def _not_yet_implemented(stage_name: str, decision_ref: str):
    def _stage(job_id: int, report_progress: Callable[[int], None], **kwargs):
        raise NotImplementedError(
            f"'{stage_name}' is not implemented yet — it is scheduled for a later build batch "
            f"once {decision_ref} is locked. See PLAN.md decision log."
        )

    return _stage


# Placeholders — intentionally raise rather than fabricate a result.
run_room_analysis = _not_yet_implemented("room_analysis", "D003 (CV strategy, deferred by D018)")
run_style_recognition = _not_yet_implemented("style_recognition", "D005 (locked: CLIP-RN50 zero-shot; wiring deferred by D018)")
run_visualization = _not_yet_implemented("visualization", "D010 (render conditioning, Batch 3)")
