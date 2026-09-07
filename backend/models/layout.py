"""
layouts, layout_objects — Layer 4 (Layout Optimization), decisions D008/D009.

This is the schema for the project's one from-scratch algorithmic
contribution (see PLAN.md "Emerging Project Thesis"). `score_breakdown` must
store every weighted term of the objective function so the UI can render a
transparent score breakdown (brief PART 16), not just a single opaque number.
`constraints_satisfied` records which hard constraints (no overlap, stays in
bounds, clearance maintained, etc.) held for this layout — again, so it can
be shown rather than merely asserted.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Layout(Base, TimestampMixin):
    __tablename__ = "layouts"

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(
        ForeignKey("recommendations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    layout_score: Mapped[float] = mapped_column(Float, nullable=False)
    # e.g. {"space_utilization": 0.34, "accessibility": 0.22, "movement_flow": 0.15,
    #       "visual_balance": 0.19, "functionality": 0.10, "overlap_penalty": 0.0,
    #       "obstruction_penalty": 0.0} — weights themselves fixed by D009.
    score_breakdown: Mapped[dict] = mapped_column(JSONB, nullable=False)
    # e.g. {"no_overlap": true, "within_bounds": true, "doors_clear": true,
    #       "min_clearance_cm": true}
    constraints_satisfied: Mapped[dict] = mapped_column(JSONB, nullable=False)

    algorithm: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. "simulated_annealing"
    iterations: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    recommendation: Mapped["Recommendation"] = relationship(back_populates="layouts")  # noqa: F821
    objects: Mapped[list["LayoutObject"]] = relationship(
        back_populates="layout", cascade="all, delete-orphan"
    )
    visualizations: Mapped[list["Visualization"]] = relationship(  # noqa: F821
        back_populates="layout", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Layout id={self.id} score={self.layout_score:.3f} algorithm={self.algorithm!r}>"


class LayoutObject(Base):
    __tablename__ = "layout_objects"

    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(
        ForeignKey("layouts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Null when this object is an existing/kept piece of furniture rather than
    # a new catalog recommendation (see `is_existing`).
    catalog_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("furniture_catalog.id", ondelete="SET NULL"), nullable=True
    )

    label: Mapped[str] = mapped_column(String(100), nullable=False)
    x_cm: Mapped[float] = mapped_column(Float, nullable=False)
    y_cm: Mapped[float] = mapped_column(Float, nullable=False)
    width_cm: Mapped[float] = mapped_column(Float, nullable=False)
    depth_cm: Mapped[float] = mapped_column(Float, nullable=False)
    rotation_deg: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    is_existing: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    layout: Mapped["Layout"] = relationship(back_populates="objects")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<LayoutObject id={self.id} label={self.label!r} pos=({self.x_cm},{self.y_cm})>"
