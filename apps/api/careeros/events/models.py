from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.clock import utcnow
from careeros.db.base import Base, UUIDPrimaryKey, enum_type


class EventType(StrEnum):
    """Spec §45, plus discovery lifecycle events for the activity feed."""

    DISCOVERY_STARTED = "DISCOVERY_STARTED"
    DISCOVERY_COMPLETED = "DISCOVERY_COMPLETED"
    DISCOVERY_FAILED = "DISCOVERY_FAILED"
    JOB_DISCOVERED = "JOB_DISCOVERED"
    JOB_NORMALIZED = "JOB_NORMALIZED"
    JOB_DEDUPLICATED = "JOB_DEDUPLICATED"
    JOB_ANALYZED = "JOB_ANALYZED"
    JOB_MATCHED = "JOB_MATCHED"
    NOTIFICATION_CREATED = "NOTIFICATION_CREATED"
    COMPANY_RESEARCH_REQUESTED = "COMPANY_RESEARCH_REQUESTED"
    COMPANY_RESEARCH_COMPLETED = "COMPANY_RESEARCH_COMPLETED"
    CONTACT_DISCOVERED = "CONTACT_DISCOVERED"
    OUTREACH_DRAFT_CREATED = "OUTREACH_DRAFT_CREATED"
    OUTREACH_APPROVAL_REQUIRED = "OUTREACH_APPROVAL_REQUIRED"
    OUTREACH_APPROVED = "OUTREACH_APPROVED"
    OUTREACH_SENT = "OUTREACH_SENT"
    OUTREACH_REPLY_DETECTED = "OUTREACH_REPLY_DETECTED"
    OUTREACH_FOLLOW_UP_DUE = "OUTREACH_FOLLOW_UP_DUE"
    RESUME_REQUESTED = "RESUME_REQUESTED"
    RESUME_GENERATED = "RESUME_GENERATED"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    APPLICATION_WAITING_FOR_USER = "APPLICATION_WAITING_FOR_USER"
    APPLICATION_READY = "APPLICATION_READY"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"


class DomainEvent(UUIDPrimaryKey, Base):
    """Append-only event log. Entity references are plain ids (history outlives entities)."""

    __tablename__ = "domain_events"
    __table_args__ = (
        Index("ix_domain_events_user_created", "user_id", "created_at"),
        Index("ix_domain_events_job", "job_id"),
        Index("ix_domain_events_application", "application_id"),
        Index("ix_domain_events_outreach", "outreach_id"),
    )

    type: Mapped[EventType] = mapped_column(enum_type(EventType))
    user_id: Mapped[uuid.UUID | None]
    job_id: Mapped[uuid.UUID | None]
    company_id: Mapped[uuid.UUID | None]
    application_id: Mapped[uuid.UUID | None]
    outreach_id: Mapped[uuid.UUID | None]
    task_id: Mapped[uuid.UUID | None]
    summary: Mapped[str] = mapped_column(String(500))
    payload: Mapped[dict[str, Any]] = mapped_column(default=dict)
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
