"""
Translates between the DB rows (RoomAnalysis/DetectedObject/StylePrediction)
and the in-memory RoomModel used by recommendation/layout_optimization —
and back — for both the dev-only fixture path (persist_fixture) and real CV
output (persist_real_cv_detections, 2026-09-08).

`load_room_model_from_db` only builds existing_furniture/openings from
cm-based DetectedObject rows (DetectionSource.DETECTION/SEGMENTATION,
fixtures only) — real CV rows are pixel-space and deliberately excluded, per
Report Issue R-10: a single 2D photo has no depth information, so a pixel
bounding box cannot honestly be turned into a real (x, y) position or exact
size. See persist_real_cv_detections for what real detections DO affect
(free_space_ratio, "area-only reservation") versus what they still don't
(no positioned "existing" object is ever fabricated).
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai.room_analysis.room_model import FurnitureItem, Opening, RoomModel
from ai.room_analysis.fixtures import RoomFixture
from backend.models.catalog import FurnitureCatalogItem
from backend.models.room import DetectedObject, DetectionSource, RoomAnalysis, RoomImage, ScaleSource
from backend.models.session import DesignSession
from backend.models.style import StylePrediction

FIXTURE_MODEL_NAME_PREFIX = "fixture:"

# Same operating point as ai.room_analysis.detection.CONFIDENCE_THRESHOLD —
# a detection below this already isn't shown to the user, so it shouldn't
# count toward the reserved-space estimate either (no separate, unmeasured
# threshold invented just for this).
RESERVATION_CONFIDENCE_THRESHOLD = 0.35

# 2026-09-08 "area-only reservation" decision: a single 2D photo has no
# depth information, so a detection's pixel bounding box cannot honestly be
# converted into a real-world position OR size (an object's apparent pixel
# size depends on its unknown distance from the camera) — see PLAN.md.
# Rather than fabricate a position/size, only detection CLASSES with a
# clearly-corresponding catalog category get a footprint estimate at all,
# taken from the project's own real (seeded) catalog data — not a guessed
# number. Every other detected class (tv, sink, book, clock, vase,
# refrigerator, potted plant) remains display-only and reserves nothing.
DETECTION_TO_CATALOG_CATEGORY = {
    "chair": "chair",
    "couch": "sofa",
    "bed": "bed",
    "dining table": "table",
}

MIN_FREE_SPACE_RATIO = 0.15  # never let noisy detections zero out all usable space


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


def _mean_catalog_footprint_cm2(db: Session, category: str) -> float | None:
    result = db.execute(
        select(FurnitureCatalogItem.width_cm, FurnitureCatalogItem.depth_cm)
        .where(FurnitureCatalogItem.category == category)
    ).all()
    if not result:
        return None
    return sum(w * d for w, d in result) / len(result)


def _estimate_reserved_area_cm2(db: Session, detections: list) -> float:
    """Estimated real-world floor area already occupied by confidently-
    detected furniture, using the mean footprint of real catalog items in
    the corresponding category as a stand-in for the detected item's actual
    size (see DETECTION_TO_CATALOG_CATEGORY's docstring above for why a
    pixel bounding box can't give us that directly). Classes with no mapped
    category contribute 0. `detections` may be either fresh
    ai.room_analysis.detection.Detection objects (initial persist) or
    DetectedObject rows already confirmed/unconfirmed (recompute after a
    confirmation) — both expose .confidence and .class_label. Any row with
    confirmed geometry is excluded: it's precisely accounted for as a real
    positioned object instead (see load_room_model_from_db), so reserving
    its area here too would double-count it."""
    total = 0.0
    for det in detections:
        if getattr(det, "confirmed_width_cm", None) is not None:
            continue
        if det.confidence < RESERVATION_CONFIDENCE_THRESHOLD:
            continue
        category = DETECTION_TO_CATALOG_CATEGORY.get(det.class_label)
        if category is None:
            continue
        mean_area = _mean_catalog_footprint_cm2(db, category)
        if mean_area:
            total += mean_area
    return total


def _recompute_free_space_ratio(db: Session, analysis: RoomAnalysis) -> None:
    """(Re)derives free_space_ratio from every REAL_DETECTION row currently
    on `analysis` — called at initial persist time and again whenever a
    detection's geometry is confirmed (confirmed rows drop out of the
    reservation at that point, see _estimate_reserved_area_cm2)."""
    if analysis.room_width_cm is None or analysis.room_length_cm is None:
        return
    room_area_cm2 = analysis.room_width_cm * analysis.room_length_cm
    if room_area_cm2 <= 0:
        return
    real_detections = [obj for obj in analysis.detected_objects if obj.source == DetectionSource.REAL_DETECTION]
    reserved_area_cm2 = _estimate_reserved_area_cm2(db, real_detections)

    from ai.recommendation.scoring import DEFAULT_FREE_SPACE_RATIO

    if reserved_area_cm2 > 0:
        reserved_ratio = reserved_area_cm2 / room_area_cm2
        analysis.free_space_ratio = max(MIN_FREE_SPACE_RATIO, DEFAULT_FREE_SPACE_RATIO - reserved_ratio)
    else:
        analysis.free_space_ratio = None


class UnconfirmableDetectionError(ValueError):
    """Raised when a DetectedObject can't become a positioned existing
    object — wrong source, unmapped class, or low confidence."""


def confirm_detected_object_geometry(
    db: Session,
    detected_object: DetectedObject,
    *,
    width_cm: float,
    depth_cm: float,
    height_cm: float,
    x_cm: float,
    y_cm: float,
    rotation_deg: int,
) -> None:
    """The one honest path from a real detection to a positioned existing
    FurnitureItem (2026-09-08, "optional from the results page" decision):
    every number here is USER-PROVIDED, not derived from the pixel bbox —
    that's what makes it safe to place, unlike the raw detection alone.
    Recomputes free_space_ratio afterward so this item's area-only
    reservation (if any) doesn't double-count alongside its new placement."""
    if detected_object.source != DetectionSource.REAL_DETECTION:
        raise UnconfirmableDetectionError("Only a real furniture detection can be confirmed.")
    if detected_object.class_label not in DETECTION_TO_CATALOG_CATEGORY:
        raise UnconfirmableDetectionError(
            f"{detected_object.class_label!r} has no corresponding catalog category to place it as."
        )
    if detected_object.confidence < RESERVATION_CONFIDENCE_THRESHOLD:
        raise UnconfirmableDetectionError("This detection's confidence is too low to confirm.")

    detected_object.confirmed_width_cm = width_cm
    detected_object.confirmed_depth_cm = depth_cm
    detected_object.confirmed_height_cm = height_cm
    detected_object.confirmed_x_cm = x_cm
    detected_object.confirmed_y_cm = y_cm
    detected_object.confirmed_rotation_deg = rotation_deg

    _recompute_free_space_ratio(db, detected_object.analysis)
    db.commit()


def persist_real_cv_detections(db: Session, analysis: RoomAnalysis, image_path: str) -> None:
    """Real furniture detection (ai.room_analysis.detection, pretrained COCO
    YOLO) + architectural segmentation (ai.room_analysis.segmentation,
    pretrained ADE20K SegFormer) for a genuine uploaded photo — 2026-09-08
    CV batch, FR-2/Report Issue R-07.

    Detected objects are persisted as DetectionSource.REAL_DETECTION/
    REAL_SEGMENTATION rows, which `load_room_model_from_db` deliberately
    skips when building existing_furniture/openings — a single 2D photo
    can't honestly provide a real (x, y) position or exact size for a
    detected item (no depth information), so nothing here ever places a
    positioned "existing" object in the layout. That stays true even with
    the "area-only reservation" decision below.

    What DOES change (2026-09-08, amending the original "detect & display
    only, zero effect on generation" scope once detection quality had
    actually been measured — see PLAN.md): confidently-detected furniture
    with a class that maps to a real catalog category (chair, sofa, bed,
    table) reduces `analysis.free_space_ratio` by that category's mean real
    footprint from the actual seeded catalog — not a fabricated number, and
    never a claimed position. This only runs when room dimensions are known
    (needed to turn an absolute cm² reservation into a ratio); a real photo
    with real detections but no dimensions still can't be scored at all,
    exactly as before this decision."""
    from ai.room_analysis.detection import detect_objects
    from ai.room_analysis.segmentation import segment_architecture

    detections = detect_objects(image_path)
    for detection in detections:
        db.add(
            DetectedObject(
                analysis_id=analysis.id,
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
                analysis_id=analysis.id,
                class_label=region.class_label,
                confidence=region.confidence,
                source=DetectionSource.REAL_SEGMENTATION,
                bbox={**region.bbox_px, "polygon": region.polygon_px},
                area_px=region.area_px,
            )
        )

    db.flush()  # so analysis.detected_objects includes the rows just added
    _recompute_free_space_ratio(db, analysis)
    db.commit()


def load_room_model_from_db(db: Session, analysis: RoomAnalysis, room_type: str) -> LoadedAnalysis:
    openings: list[Opening] = []
    furniture: list[FurnitureItem] = []
    for obj in analysis.detected_objects:
        if obj.source == DetectionSource.REAL_DETECTION and obj.confirmed_width_cm is not None:
            # The ONE path by which real CV output becomes a genuinely
            # positioned existing object — every field here is user-
            # confirmed (see confirm_detected_object_geometry), not derived
            # from the pixel bbox, so it's honest in a way the raw detection
            # never could be on its own.
            furniture.append(
                FurnitureItem(
                    label=obj.class_label, width_cm=obj.confirmed_width_cm, depth_cm=obj.confirmed_depth_cm,
                    height_cm=obj.confirmed_height_cm, x_cm=obj.confirmed_x_cm, y_cm=obj.confirmed_y_cm,
                    rotation_deg=obj.confirmed_rotation_deg or 0,
                    is_existing=True, category=DETECTION_TO_CATALOG_CATEGORY.get(obj.class_label),
                )
            )
            continue
        if obj.source in (DetectionSource.REAL_DETECTION, DetectionSource.REAL_SEGMENTATION):
            # Never fed into existing_furniture/openings — see
            # persist_real_cv_detections for why (no depth information in a
            # single photo). free_space_ratio (read below) is the one real
            # effect these rows can have, already applied at persist time.
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
