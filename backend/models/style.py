"""
style_predictions — Layer 3, interior style recognition (FR-3, decision D005).

Stores one prediction per room_analysis, including a full alternatives list
and an explicit `abstained` flag: brief PART 4 requires the system to say
"I don't know" rather than assert a style with false certainty when
confidence is low. The abstain threshold itself is an ai/style_recognition
implementation detail (Batch 2), not something this schema hardcodes.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class StylePrediction(Base, TimestampMixin):
    __tablename__ = "style_predictions"

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(
        ForeignKey("room_analyses.id", ondelete="CASCADE"), index=True, nullable=False
    )

    predicted_style: Mapped[str] = mapped_column(String(50), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    # [{"style": "Contemporary", "confidence": 0.09}, ...] — full softmax,
    # not just the top-1, so the UI can render brief PART 4's
    # "Alternative: Contemporary — 9%" display.
    alternatives: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    analysis: Mapped["RoomAnalysis"] = relationship(back_populates="style_predictions")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<StylePrediction style={self.predicted_style!r} conf={self.confidence:.2f}>"
