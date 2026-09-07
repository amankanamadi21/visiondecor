"""
users, user_preferences — identity and stored per-user defaults.

Passwords are never stored in plaintext or reversibly encrypted: only an
argon2 hash (see backend/services/auth_service.py) is persisted, satisfying
brief PART 21 / report NFR-2.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, String, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, utcnow


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    preferences: Mapped[Optional["UserPreference"]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    design_sessions: Mapped[list["DesignSession"]] = relationship(  # noqa: F821
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"


class UserPreference(Base):
    """
    Stored defaults that pre-fill the preference form on a new design (brief
    PART 5 / FR-1). NOT the per-session preferences of an individual design —
    those live on DesignSession — this is only the user's remembered defaults.
    """

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True, nullable=False
    )

    default_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # JSONB list of hex colors / color names, e.g. ["#E5DCC5", "warm neutrals"]
    default_colors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    default_budget: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="preferences")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<UserPreference user_id={self.user_id} style={self.default_style!r}>"
