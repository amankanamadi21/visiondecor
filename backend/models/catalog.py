"""
furniture_catalog — Layer 3 furniture data.

2026-09-09: replaced with real, purchasable products (manually researched
from real Indian retailers — IKEA India, Urban Ladder, Pepperfry, Home
Centre, Obeetee, Homesake — not scraped, not fabricated; see PLAN.md for the
full research methodology). `data_source='REAL'` plus `price_verified_at`
records exactly when each price/link was confirmed, so a stale price reads
as stale rather than as a live one — the same honesty discipline this
project has always applied to `MOCK`/`estimated`/`user-provided` labels, now
pointed the other way: the risk here is a real price/link going stale, not
a fake one being mistaken for real. `data_source='MOCK'` remains a valid,
supported value (the column is a plain string, not an enum) for any future
row that genuinely is placeholder data — it is simply not used by the
current seed data. Dimensions (width_cm/depth_cm/height_cm) are NOT
optional: the layout optimiser (Layer 4) cannot place an item it doesn't
know the physical size of, so a catalog row without dimensions is not a
valid catalog row.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from sqlalchemy import Date, Float, Numeric, String
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

    # A real link to the actual retailer product page (2026-09-09) — null
    # only for a genuinely MOCK row, never for a REAL one.
    product_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # The date this row's price/link/dimensions were actually checked against
    # the live retailer page — the disclosure that makes a real price honest
    # over time (see module docstring). Null for MOCK rows.
    price_verified_at: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # 'REAL' (default, as of 2026-09-09) or 'MOCK' — see module docstring.
    data_source: Mapped[str] = mapped_column(String(10), default="REAL", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FurnitureCatalogItem id={self.id} name={self.name!r} price={self.price}>"
