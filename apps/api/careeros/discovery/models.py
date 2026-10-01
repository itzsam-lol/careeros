from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey, enum_type


class SourceType(StrEnum):
    GREENHOUSE = "GREENHOUSE"
    LEVER = "LEVER"
    ASHBY = "ASHBY"
    SMARTRECRUITERS = "SMARTRECRUITERS"
    WORKDAY = "WORKDAY"
    ORACLE_CLOUD = "ORACLE_CLOUD"
    AMAZON = "AMAZON"
    RSS = "RSS"
    CAREER_PAGE = "CAREER_PAGE"
    FIXTURE = "FIXTURE"


class DiscoveryCadence(StrEnum):
    MANUAL = "MANUAL"
    EVERY_15_MIN = "EVERY_15_MIN"
    EVERY_30_MIN = "EVERY_30_MIN"
    HOURLY = "HOURLY"
    EVERY_6_HOURS = "EVERY_6_HOURS"
    DAILY = "DAILY"


CADENCE_INTERVALS: dict[DiscoveryCadence, timedelta | None] = {
    DiscoveryCadence.MANUAL: None,
    DiscoveryCadence.EVERY_15_MIN: timedelta(minutes=15),
    DiscoveryCadence.EVERY_30_MIN: timedelta(minutes=30),
    DiscoveryCadence.HOURLY: timedelta(hours=1),
    DiscoveryCadence.EVERY_6_HOURS: timedelta(hours=6),
    DiscoveryCadence.DAILY: timedelta(days=1),
}


class JobSource(UUIDPrimaryKey, Timestamped, Base):
    """A user-configured place to discover jobs, with health tracking (spec §69)."""

    __tablename__ = "job_sources"
    __table_args__ = (UniqueConstraint("user_id", "identity"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    type: Mapped[SourceType] = mapped_column(enum_type(SourceType))
    config: Mapped[dict[str, Any]] = mapped_column(default=dict)
    identity: Mapped[str] = mapped_column(String(600))  # canonical "type:key" for dedupe
    enabled: Mapped[bool] = mapped_column(default=True)
    cadence: Mapped[DiscoveryCadence] = mapped_column(
        enum_type(DiscoveryCadence), default=DiscoveryCadence.DAILY
    )
    next_run_at: Mapped[datetime | None]
    last_run_at: Mapped[datetime | None]
    last_success_at: Mapped[datetime | None]
    last_failure_at: Mapped[datetime | None]
    last_error: Mapped[str | None] = mapped_column(Text)
    last_jobs_found: Mapped[int] = mapped_column(default=0)
    total_jobs_found: Mapped[int] = mapped_column(default=0)
    run_count: Mapped[int] = mapped_column(default=0)
    error_count: Mapped[int] = mapped_column(default=0)
    consecutive_failures: Mapped[int] = mapped_column(default=0)
    avg_duration_ms: Mapped[float | None] = mapped_column(Float)
