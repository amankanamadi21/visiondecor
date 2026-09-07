"""
design_sessions, jobs — a design session is one "project" (one room, one
set of preferences, potentially many recommendation/layout iterations).
jobs tracks background AI-pipeline work (Batch 1 thread-based JobRunner —
see decision log D012/jobs; stated limitation vs NFR-5: single-process only).
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin, utcnow


class SessionStatus(str, enum.Enum):
    DRAFT = "draft"  # created, image not yet uploaded / preferences incomplete
    ANALYZING = "analyzing"
    READY = "ready"  # recommendation + layout produced at least once
    ERROR = "error"


class DesignSession(Base, TimestampMixin):
    __tablename__ = "design_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    room_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    status: Mapped[SessionStatus] = mapped_column(
        Enum(SessionStatus, name="session_status"), default=SessionStatus.DRAFT, nullable=False
    )

    # Per-design preferences (FR-1/FR-4) — added post-Batch-1 to complete an
    # omission (these are needed to trigger a recommendation and had nowhere
    # to live). Distinct from UserPreference, which stores the user's
    # remembered DEFAULTS across designs, not this specific design's choices.
    preferred_style: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    preferred_colors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    budget: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)  # D019

    updated_at: Mapped[datetime] = mapped_column(default=utcnow, onupdate=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="design_sessions")  # noqa: F821
    jobs: Mapped[list["Job"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    images: Mapped[list["RoomImage"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["Recommendation"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )
    feedback_entries: Mapped[list["Feedback"]] = relationship(  # noqa: F821
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DesignSession id={self.id} user_id={self.user_id} status={self.status}>"


class JobStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"


class JobStage(str, enum.Enum):
    """One row per pipeline stage run, so the frontend can show granular
    per-stage progress rather than one opaque spinner (brief PART 15/16)."""

    PREPROCESS = "preprocess"
    ROOM_ANALYSIS = "room_analysis"
    STYLE_RECOGNITION = "style_recognition"
    RECOMMENDATION = "recommendation"
    LAYOUT_OPTIMIZATION = "layout_optimization"
    VISUALIZATION = "visualization"
    # Batch 2: recommendation + layout optimisation run as one combined job
    # (see backend/services/pipeline_stages.py:run_generate_design) rather
    # than two chained jobs — a deliberate simplification, not a schema
    # mismatch; RECOMMENDATION/LAYOUT_OPTIMIZATION remain reserved for a
    # future finer-grained progress breakdown if that's ever worth the
    # added complexity of chaining jobs across background threads.
    GENERATE_DESIGN = "generate_design"


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("design_sessions.id", ondelete="CASCADE"), index=True, nullable=False
    )

    stage: Mapped[JobStage] = mapped_column(Enum(JobStage, name="job_stage"), nullable=False)
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status"), default=JobStatus.QUEUED, nullable=False
    )
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # 0-100

    # Structured error taxonomy (brief PART 15) — machine-readable code plus a
    # human-readable, user-safe message. Never a raw stack trace.
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    session: Mapped["DesignSession"] = relationship(back_populates="jobs")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Job id={self.id} stage={self.stage} status={self.status} progress={self.progress}>"
