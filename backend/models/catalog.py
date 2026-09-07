"""
furniture_catalog — Layer 3, mock-but-schema-complete furniture data.

`data_source` is hardcoded to the literal 'MOCK' at the model level (brief
PART 6 / PART 34.15: mocked components must be clearly labelled, never
disguised as real product data). Dimensions (width_cm/depth_cm/height_cm)
are NOT optional: the layout optimiser (Layer 4) cannot place an item it
doesn't know the physical size of, so a catalog row without dimensions is
not a valid catalog row.
"""
from __future__ import annotations

from sqlalchemy import Float, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin


class FurnitureCatalogItem(Base, TimestampMixin):
    __tablename__ = "furniture_catalog"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(50), index=True, nullable=False)

    # e.g. ["Modern", "Minimalist"] — an item may suit more than one style.
    style_tags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    color: Mapped[str] = mapped_column(String(50), nullable=False)

    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    width_cm: Mapped[float] = mapped_column(Float, nullable=False)
    depth_cm: Mapped[float] = mapped_column(Float, nullable=False)
    height_cm: Mapped[float] = mapped_column(Float, nullable=False)

    image_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Fixed literal — see module docstring. Not user-editable, not derived.
    data_source: Mapped[str] = mapped_column(String(10), default="MOCK", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FurnitureCatalogItem id={self.id} name={self.name!r} price={self.price}>"
