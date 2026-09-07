"""
design_principles — Layer 3 RAG knowledge base (decision D006a).

A small curated corpus of interior-design principles (clearance standards,
style definitions, colour rules, room-type guidance). The recommendation
engine retrieves relevant rows by embedding similarity and cites `code` in
the rationale shown to the user (brief PART 16 explainability). The LLM used
in D006a only *phrases* retrieved facts — it never writes rows into this
table and never invents a principle that isn't stored here.

Requires the `vector` extension (pgvector), created in the first Alembic
migration: `CREATE EXTENSION IF NOT EXISTS vector;`
"""
from __future__ import annotations

import enum
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum as SAEnum
from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base, TimestampMixin

EMBEDDING_DIM = 384  # sentence-transformers/all-MiniLM-L6-v2 (see .env.example)


class PrincipleCategory(str, enum.Enum):
    CLEARANCE = "clearance"
    STYLE = "style"
    COLOR = "color"
    LIGHTING = "lighting"
    ROOM_TYPE = "room_type"


class DesignPrinciple(Base, TimestampMixin):
    __tablename__ = "design_principles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True, nullable=False)
    category: Mapped[PrincipleCategory] = mapped_column(
        SAEnum(PrincipleCategory, name="principle_category"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)

    # e.g. ["living_room", "bedroom"] / ["Modern", "Minimalist"] — null/empty
    # list means "applies universally".
    applies_to_room_types: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    applies_to_styles: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    source_note: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)

    embedding: Mapped[Optional[list]] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DesignPrinciple code={self.code!r} title={self.title!r}>"
