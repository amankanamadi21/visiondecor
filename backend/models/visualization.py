"""
visualizations — Layer 5, generative render output (decision D003).

`structure_preserving` is a required boolean, not a nullable/optional flag:
the UI MUST be able to tell the user whether this specific image came from
the image-editing path (Gemini — geometry preserved by construction) or a
text-to-image fallback (Cloudflare/HF — geometry not guaranteed). Silently
presenting a fallback render as equally trustworthy would violate brief
PART 15/16 and decision D003's attached condition.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class Visualization(Base, TimestampMixin):
    __tablename__ = "visualizations"

    id: Mapped[int] = mapped_column(primary_key=True)
    layout_id: Mapped[int] = mapped_column(
        ForeignKey("layouts.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # e.g. "gemini-2.5-flash-image", "cloudflare-sdxl", "cache", "floorplan-only"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    image_path: Mapped[str] = mapped_column(String(500), nullable=False)
    prompt_used: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    structure_preserving: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cache_hit: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    layout: Mapped["Layout"] = relationship(back_populates="visualizations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Visualization id={self.id} provider={self.provider!r} structure_preserving={self.structure_preserving}>"
