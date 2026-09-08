"""
Translates between the DB rows (RoomAnalysis/DetectedObject/StylePrediction)
and the in-memory RoomModel used by recommendation/layout_optimization —
and back, for the dev-only fixture-seeding path.

This is the ONLY place that reads/writes DetectedObject.bbox as cm-based
room coordinates. Real CV integration (not yet built) will populate pixel-
space detections and will need its own pixel->cm reprojection step before
storing — see Report Issue R-10 in PLAN.md — but whatever populates these
rows, `load_room_model_from_db` doesn't care: it only requires cm-based
fields to already be present, regardless of how they got there.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from ai.room_analysis.room_model import FurnitureItem, Opening, RoomModel
from ai.room_analysis.fixtures import RoomFixture
from backend.models.room import DetectedObject, DetectionSource, RoomAnalysis, RoomImage, ScaleSource
from backend.models.session import DesignSession
from backend.models.style import StylePrediction

FIXTURE_MODEL_NAME_PREFIX = "fixture:"


@dataclass
class LoadedAnalysis:
    room: RoomModel
    predicted_style: str
    style_confidence: float
    style_alternatives: list[dict]
    is_fixture: bool


def persist_fixture(db: Session, session_id: int, fixture: RoomFixture) -> RoomAnalysis:
    """DEV-ONLY. Writes a RoomImage/RoomAnalysis/DetectedObject/
    StylePrediction row set representing `fixture`, clearly tagged as
    fixture-origin via `model_versions`/`model_name` (see D018 guardrail —
    never to be confused with real detection output)."""
    design_session = db.get(DesignSession, session_id)
    if design_session is None:
        raise ValueError(f"No design_session with id={session_id}")

    room_image = RoomImage(
        session_id=session_id,
        original_path=f"FIXTURE:{fixture.name}",
        file_hash=f"fixture-{fixture.name}",
        width=None,
        height=None,
        quality_flags={"source": "fixture"},
    )
    db.add(room_image)
    db.flush()

    analysis = RoomAnalysis(
        image_id=room_image.id,
        floor_polygon=None,
        free_space_ratio=fixture.room.free_space_ratio,
        room_width_cm=fixture.room.width_cm,
        room_length_cm=fixture.room.length_cm,
        scale_source=ScaleSource.USER_PROVIDED,
        model_versions={"source": "fixture", "fixture_name": fixture.name},
    )
    db.add(analysis)
    db.flush()

    for opening in fixture.room.openings:
        db.add(
            DetectedObject(
                analysis_id=analysis.id,
                class_label=opening.kind,
                confidence=1.0,
                source=DetectionSource.SEGMENTATION,
                bbox={"wall": opening.wall, "position_cm": opening.position_cm, "width_cm": opening.width_cm},
            )
        )

    for item in fixture.room.existing_furniture:
        db.add(
            DetectedObject(
                analysis_id=analysis.id,
                class_label=item.label,
                confidence=1.0,
                source=DetectionSource.DETECTION,
                bbox={
                    "x_cm": item.x_cm, "y_cm": item.y_cm,
                    "width_cm": item.width_cm, "depth_cm": item.depth_cm, "height_cm": item.height_cm,
                    "rotation_deg": item.rotation_deg, "category": item.category,
                },
            )
        )

    db.add(
        StylePrediction(
            analysis_id=analysis.id,
            predicted_style=fixture.style.predicted_style,
            confidence=fixture.style.confidence,
            alternatives=fixture.style.alternatives,
            model_name=f"{FIXTURE_MODEL_NAME_PREFIX}{fixture.name}",
            abstained=fixture.style.abstained,
        )
    )
    db.commit()
    return analysis


def persist_real_cv_detections(db: Session, analysis_id: int, image_path: str) -> None:
    """Real furniture detection (ai.room_analysis.detection, pretrained COCO
    YOLO) + architectural segmentation (ai.room_analysis.segmentation,
    pretrained ADE20K SegFormer) for a genuine uploaded photo — 2026-09-08
    CV batch, FR-2/Report Issue R-07. Display-only this batch: rows are
    tagged DetectionSource.REAL_DETECTION/REAL_SEGMENTATION, which
    `load_room_model_from_db` deliberately skips (see below) — they do not
    affect recommendation or layout generation yet. That is a scoped,
    explicit decision (2026-09-08), not an oversight; feeding real detections
    into the optimiser as immovable existing furniture is a natural,
    separately-decided follow-up once detection quality has been observed
    on real photos."""
    from ai.room_analysis.detection import detect_objects
    from ai.room_analysis.segmentation import segment_architecture

    for detection in detect_objects(image_path):
        db.add(
            DetectedObject(
                analysis_id=analysis_id,
                class_label=detection.class_label,
                confidence=detection.confidence,
                source=DetectionSource.REAL_DETECTION,
                bbox=detection.bbox_px,
                area_px=detection.area_px,
            )
        )

    for region in segment_architecture(image_path):
        db.add(
            DetectedObject(
                analysis_id=analysis_id,
                class_label=region.class_label,
                confidence=region.confidence,
                source=DetectionSource.REAL_SEGMENTATION,
                bbox={**region.bbox_px, "polygon": region.polygon_px},
                area_px=region.area_px,
            )
        )
    db.commit()


def load_room_model_from_db(db: Session, analysis: RoomAnalysis, room_type: str) -> LoadedAnalysis:
    openings: list[Opening] = []
    furniture: list[FurnitureItem] = []
    for obj in analysis.detected_objects:
        if obj.source in (DetectionSource.REAL_DETECTION, DetectionSource.REAL_SEGMENTATION):
            # Display-only this batch (see persist_real_cv_detections) — not
            # yet fed into the RoomModel the recommendation/layout engine use.
            continue
        if obj.source == DetectionSource.SEGMENTATION and obj.class_label in ("door", "window"):
            openings.append(
                Opening(kind=obj.class_label, wall=obj.bbox["wall"], position_cm=obj.bbox["position_cm"], width_cm=obj.bbox["width_cm"])
            )
        else:
            b = obj.bbox
            furniture.append(
                FurnitureItem(
                    label=obj.class_label, width_cm=b["width_cm"], depth_cm=b["depth_cm"], height_cm=b["height_cm"],
                    x_cm=b["x_cm"], y_cm=b["y_cm"], rotation_deg=b.get("rotation_deg", 0),
                    is_existing=True, category=b.get("category"),
                )
            )

    room = RoomModel(
        room_type=room_type,
        width_cm=analysis.room_width_cm,
        length_cm=analysis.room_length_cm,
        openings=openings,
        existing_furniture=furniture,
        free_space_ratio=analysis.free_space_ratio,
    )

    style_pred = analysis.style_predictions[-1] if analysis.style_predictions else None
    is_fixture = analysis.model_versions is not None and analysis.model_versions.get("source") == "fixture"

    return LoadedAnalysis(
        room=room,
        predicted_style=style_pred.predicted_style if style_pred else room_type,
        style_confidence=style_pred.confidence if style_pred else 0.0,
        style_alternatives=style_pred.alternatives if style_pred else [],
        is_fixture=is_fixture,
    )
