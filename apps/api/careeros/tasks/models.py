from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.clock import utcnow
from careeros.db.base import Base, Timestamped, UUIDPrimaryKey, enum_type


class TaskStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


TERMINAL_STATUSES = frozenset({TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED})


class TaskType(StrEnum):
    RUN_DISCOVERY = "RUN_DISCOVERY"
    ANALYZE_JOB = "ANALYZE_JOB"
    MATCH_JOB = "MATCH_JOB"
    INDEX_PROFILE = "INDEX_PROFILE"
    GENERATE_RESUME = "GENERATE_RESUME"
    RESEARCH_COMPANY = "RESEARCH_COMPANY"
    DISCOVER_CONTACTS = "DISCOVER_CONTACTS"
    DRAFT_OUTREACH = "DRAFT_OUTREACH"
    SEND_OUTREACH = "SEND_OUTREACH"
    CHECK_OUTREACH = "CHECK_OUTREACH"
    CHECK_DEADLINES = "CHECK_DEADLINES"
    PREPARE_APPLICATION = "PREPARE_APPLICATION"
    SUBMIT_APPLICATION = "SUBMIT_APPLICATION"


class AgentTask(UUIDPrimaryKey, Timestamped, Base):
    """A unit of background work (spec §65). The row is the source of truth for its state."""

    __tablename__ = "agent_tasks"
    __table_args__ = (
        Index("ix_agent_tasks_claim", "status", "run_after", "priority"),
        Index("ix_agent_tasks_user_created", "user_id", "created_at"),
        Index(
            "uq_agent_tasks_idempotency_key",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[TaskType] = mapped_column(enum_type(TaskType))
    status: Mapped[TaskStatus] = mapped_column(enum_type(TaskStatus), default=TaskStatus.QUEUED)
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    result: Mapped[dict[str, Any] | None]
    error: Mapped[str | None] = mapped_column(Text)
    error_type: Mapped[str | None] = mapped_column(String(80))
    attempt_count: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)
    priority: Mapped[int] = mapped_column(default=0)
    run_after: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    locked_by: Mapped[str | None] = mapped_column(String(120))
    locked_until: Mapped[datetime | None]
    started_at: Mapped[datetime | None]
    completed_at: Mapped[datetime | None]
