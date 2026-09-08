"""
room_images, room_analyses, detected_objects — Layer 2 (Image Analysis).

`RoomAnalysis.scale_source` is a required, non-optional column: brief PART 3
and Report Issue R-10 both forbid presenting an estimated or user-provided
measurement as if it were measured from the image. Every consumer of room
dimensions (recommendation, layout optimisation, the UI) must read this
column and label the value accordingly.
"""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Enum as SAEnum
from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class RoomImage(Base, TimestampMixin):
    __tablename__ = "room_images"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("design_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    original_path: Mapped[str] = mapped_column(String(500), nullable=False)
    processed_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    width: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    height: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # SHA-256 of the original file bytes — used for dedupe and to detect
    # tampering between upload and processing.
    file_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    # e.g. {"too_dark": false, "too_blurry": false, "low_resolution": false}
    quality_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    session: Mapped["DesignSession"] = relationship(back_populates="images")  # noqa: F821
    analyses: Mapped[list["RoomAnalysis"]] = relationship(
        back_populates="image", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RoomImage id={self.id} session_id={self.session_id}>"


class ScaleSource(str, enum.Enum):
    """Provenance of room_width_cm / room_length_cm — see module docstring."""

    USER_PROVIDED = "user_provided"
    ESTIMATED = "estimated"
    UNKNOWN = "unknown"


class RoomAnalysis(Base, TimestampMixin):
    __tablename__ = "room_analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    image_id: Mapped[int] = mapped_column(
        ForeignKey("room_images.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Polygon of the segmented floor area, in image pixel coordinates:
    # [[x1,y1], [x2,y2], ...]. Used to compute free_space_ratio and to derive
    # the deterministic floor-plan render.
    floor_polygon: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    free_space_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    room_width_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    room_length_cm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    scale_source: Mapped[ScaleSource] = mapped_column(
        SAEnum(ScaleSource, name="scale_source"),
        default=ScaleSource.UNKNOWN,
        nullable=False,
    )

    # {"detector": "yolov8n", "detector_version": "...", "segmenter": "...", ...}
    model_versions: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    image: Mapped["RoomImage"] = relationship(back_populates="analyses")
    detected_objects: Mapped[list["DetectedObject"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan"
    )
    style_predictions: Mapped[list["StylePrediction"]] = relationship(  # noqa: F821
        back_populates="analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RoomAnalysis id={self.id} scale_source={self.scale_source}>"


class DetectionSource(str, enum.Enum):
    DETECTION = "detection"  # cm-space, dev fixture rows only (persist_fixture)
    SEGMENTATION = "segmentation"  # cm-space, dev fixture rows only (persist_fixture)
    # Genuine CV output for a real uploaded photo (2026-09-08 batch), pixel-
    # space bbox. Never turned into a positioned "existing" FurnitureItem by
    # load_room_model_from_db — no depth info in a single photo to place one
    # honestly — but confident detections DO reduce free_space_ratio via an
    # "area-only reservation" at persist time; see persist_real_cv_detections.
    REAL_DETECTION = "real_detection"  # YOLO bounding box
    REAL_SEGMENTATION = "real_segmentation"  # wall/floor/ceiling/window/door mask


class DetectedObject(Base):
    __tablename__ = "detected_objects"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("room_analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    class_label: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    # Detection: {"x": .., "y": .., "w": .., "h": ..} in pixels.
    # Segmentation: polygon or RLE mask, model-dependent.
    bbox: Mapped[dict] = mapped_column(JSONB, nullable=False)
    source: Mapped[DetectionSource] = mapped_column(
        SAEnum(DetectionSource, name="detection_source"), nullable=False
    )
    area_px: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    analysis: Mapped["RoomAnalysis"] = relationship(back_populates="detected_objects")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DetectedObject id={self.id} class={self.class_label!r} conf={self.confidence:.2f}>"
