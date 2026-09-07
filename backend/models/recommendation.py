"""
recommendations, recommendation_items — Layer 3 output.

`score_breakdown` on each item stores the individual scoring components
(style match, budget fit, space fit, etc.) that the deterministic rationale
template (decision D007a) renders into human-readable text — e.g. "Matches
your Modern preference (0.91) · fits available space (0.78) · within budget".
This keeps the rationale provably derived from real numbers rather than
free-form, unverifiable prose.
"""
from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.catalog import FurnitureCatalogItem

from backend.models.base import Base, TimestampMixin


class Recommendation(Base, TimestampMixin):
    __tablename__ = "recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("design_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # Increments each time feedback triggers a re-run (brief PART 10 / FR-7),
    # so iteration 1, 2, 3... of the same session can be compared (FR-9 A/B).
    iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    total_cost: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    budget: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    within_budget: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # e.g. {"primary": "#E5DCC5", "accent": "#3A3A3A", "neutral": "#FFFFFF"}
    palette: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    session: Mapped["DesignSession"] = relationship(back_populates="recommendations")  # noqa: F821
    items: Mapped[list["RecommendationItem"]] = relationship(
        back_populates="recommendation", cascade="all, delete-orphan"
    )
    layouts: Mapped[list["Layout"]] = relationship(  # noqa: F821
        back_populates="recommendation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation id={self.id} iteration={self.iteration} within_budget={self.within_budget}>"


class RecommendationAction(str, enum.Enum):
    ADD = "add"
    KEEP = "keep"
    REMOVE = "remove"
    REPLACE = "replace"


class RecommendationItem(Base):
    __tablename__ = "recommendation_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("furniture_catalog.id", ondelete="RESTRICT"), nullable=False
    )
    catalog_item: Mapped["FurnitureCatalogItem"] = relationship()

    action: Mapped[RecommendationAction] = mapped_column(
        SAEnum(RecommendationAction, name="recommendation_action"), nullable=False
    )
    # e.g. {"style_match": 0.91, "space_fit": 0.78, "budget_fit": 1.0,
    #       "color_match": 0.65, "principle_citations": ["CP-04", "CL-02"]}
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="items")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RecommendationItem id={self.id} action={self.action} catalog_item_id={self.catalog_item_id}>"
