from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey


class JobMatch(UUIDPrimaryKey, Timestamped, Base):
    """The latest match of a user's profile against a job (spec §17). Not a hiring probability."""

    __tablename__ = "job_matches"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id"),
        Index("ix_job_matches_user_score", "user_id", "overall_score"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="CASCADE")
    )
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_analyses.id", ondelete="SET NULL")
    )
    profile_version: Mapped[int]
    eligible: Mapped[bool]
    eligibility: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    overall_score: Mapped[float] = mapped_column(Float)
    dimensions: Mapped[dict[str, Any]] = mapped_column(default=dict)
    strengths: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    gaps: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    concerns: Mapped[list[str]] = mapped_column(default=list)
    reasoning: Mapped[str] = mapped_column(Text, default="")
    requirement_coverage: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    evidence: Mapped[list[dict[str, Any]]] = mapped_column(default=list)
    scorer: Mapped[str] = mapped_column(String(160))
