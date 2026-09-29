from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.enums import CompensationPeriod, EmploymentType, RemoteType, SeniorityLevel
from careeros.db.base import EMBEDDING_DIM, Base, Timestamped, UUIDPrimaryKey, enum_type

_EMPTY_LIST = text("'[]'::jsonb")


class ApplicationPlatform(StrEnum):
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    ASHBY = "ASHBY"
    WORKDAY = "WORKDAY"
    SMARTRECRUITERS = "SMARTRECRUITERS"
    GOOGLE_FORMS = "GOOGLE_FORMS"
    WORKABLE = "WORKABLE"
    ICIMS = "ICIMS"
    TALEO = "TALEO"
    LINKEDIN = "LINKEDIN"
    EMAIL = "EMAIL"
    GENERIC = "GENERIC"
    UNKNOWN = "UNKNOWN"


class AnalysisStatus(StrEnum):
    PENDING = "PENDING"
    ANALYZED = "ANALYZED"
    FAILED = "FAILED"


class JobLifecycle(StrEnum):
    """Per-user job lifecycle (spec §77). Kept separate from application/outreach states."""

    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    MATCHED = "MATCHED"
    NOTIFIED = "NOTIFIED"
    SAVED = "SAVED"
    DISMISSED = "DISMISSED"
    CLOSED = "CLOSED"


class Job(UUIDPrimaryKey, Timestamped, Base):
    """A canonical, de-duplicated opportunity (spec §14). Shared by all users."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index(
            "uq_jobs_canonical_url",
            "canonical_url",
            unique=True,
            postgresql_where=text("canonical_url IS NOT NULL"),
        ),
        Index("ix_jobs_dedup_key", "dedup_key"),
        Index("ix_jobs_description_hash", "description_hash"),
        Index("ix_jobs_company_title", "company_id", "normalized_title"),
        Index("ix_jobs_posted_at", "posted_at"),
        Index("ix_jobs_is_active", "is_active"),
        Index("ix_jobs_external_id", "external_id"),
        Index(
            "ix_jobs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    company_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL")
    )
    company: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    normalized_title: Mapped[str] = mapped_column(String(300))
    location: Mapped[str | None] = mapped_column(String(300))
    locations: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    normalized_location: Mapped[str] = mapped_column(String(300), default="")
    countries: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    employment_type: Mapped[EmploymentType | None] = mapped_column(enum_type(EmploymentType))
    remote_type: Mapped[RemoteType] = mapped_column(
        enum_type(RemoteType), default=RemoteType.UNKNOWN
    )
    seniority: Mapped[SeniorityLevel] = mapped_column(
        enum_type(SeniorityLevel), default=SeniorityLevel.UNKNOWN
    )
    department: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    description_hash: Mapped[str] = mapped_column(String(64))
    posted_at: Mapped[datetime | None]
    deadline: Mapped[datetime | None]
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    currency: Mapped[str | None] = mapped_column(String(3))
    salary_period: Mapped[CompensationPeriod | None] = mapped_column(enum_type(CompensationPeriod))
    canonical_url: Mapped[str | None] = mapped_column(String(1000))
    external_id: Mapped[str | None] = mapped_column(String(200))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL")
    )
    application_url: Mapped[str | None] = mapped_column(String(1000))
    application_platform: Mapped[ApplicationPlatform] = mapped_column(
        enum_type(ApplicationPlatform), default=ApplicationPlatform.UNKNOWN
    )
    raw_metadata: Mapped[dict[str, Any]] = mapped_column(default=dict)
    dedup_key: Mapped[str] = mapped_column(String(700))
    first_seen_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]
    is_active: Mapped[bool] = mapped_column(default=True)
    closed_at: Mapped[datetime | None]
    analysis_status: Mapped[AnalysisStatus] = mapped_column(
        enum_type(AnalysisStatus), default=AnalysisStatus.PENDING
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_model: Mapped[str | None] = mapped_column(String(160))


class JobSourceLink(UUIDPrimaryKey, Base):
    """Where a canonical job was seen (spec §15: store source mappings)."""

    __tablename__ = "job_source_links"
    __table_args__ = (
        UniqueConstraint("source_id", "external_id"),
        Index("ix_job_source_links_job", "job_id"),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="CASCADE")
    )
    source_type: Mapped[str] = mapped_column(String(40))
    external_id: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(1000))
    active: Mapped[bool] = mapped_column(default=True)
    first_seen_at: Mapped[datetime]
    last_seen_at: Mapped[datetime]


class UserJob(UUIDPrimaryKey, Timestamped, Base):
    """A user's relationship with an opportunity (their inbox entry)."""

    __tablename__ = "user_jobs"
    __table_args__ = (
        UniqueConstraint("user_id", "job_id"),
        Index("ix_user_jobs_user_status", "user_id", "status"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"))
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("job_sources.id", ondelete="SET NULL")
    )
    status: Mapped[JobLifecycle] = mapped_column(
        enum_type(JobLifecycle), default=JobLifecycle.DISCOVERED
    )
    saved_at: Mapped[datetime | None]
    dismissed_at: Mapped[datetime | None]
    dismiss_reason: Mapped[str | None] = mapped_column(String(200))
    notified_at: Mapped[datetime | None]
    first_seen_at: Mapped[datetime]
    note: Mapped[str | None] = mapped_column(Text)
