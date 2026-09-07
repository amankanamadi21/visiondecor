"""
feedback — Layer 5, user feedback (FR-7, decisions D007a/D011a).

`raw_text` is exactly what the user typed. `structured_deltas` is what a free
text-parsing LLM extracted from it, schema-validated before being written
here (see backend/services/feedback_service.py, built in Batch 3). The LLM
that produces structured_deltas never touches furniture selection, price, or
position directly — those fields only ever describe what to RE-RUN with, the
actual re-computation happens in the deterministic recommendation/layout
modules.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Feedback(Base, TimestampMixin):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("design_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    recommendation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )

    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # e.g. {"keep_items": [12], "remove_items": [7], "style_shift": "more_minimalist",
    #       "budget_delta": -2000, "notes": "less crowded"}
    structured_deltas: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5, optional

    session: Mapped["DesignSession"] = relationship(back_populates="feedback_entries")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Feedback id={self.id} session_id={self.session_id} rating={self.rating}>"
