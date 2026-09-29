from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.clock import utcnow
from careeros.db.base import Base, UUIDPrimaryKey


class AuditAction(StrEnum):
    PROFILE_UPDATED = "PROFILE_UPDATED"
    PROFILE_IMPORTED = "PROFILE_IMPORTED"
    PROFILE_ITEM_VERIFIED = "PROFILE_ITEM_VERIFIED"
    SETTINGS_UPDATED = "SETTINGS_UPDATED"
    SOURCE_CREATED = "SOURCE_CREATED"
    SOURCE_UPDATED = "SOURCE_UPDATED"
    SOURCE_DELETED = "SOURCE_DELETED"
    DISCOVERY_TRIGGERED = "DISCOVERY_TRIGGERED"
    RESUME_REQUESTED = "RESUME_REQUESTED"
    RESUME_GENERATED = "RESUME_GENERATED"
    RESUME_APPROVED = "RESUME_APPROVED"
    COMPANY_RESEARCH_REQUESTED = "COMPANY_RESEARCH_REQUESTED"
    CONTACT_ADDED = "CONTACT_ADDED"
    EMAIL_DRAFT_CREATED = "EMAIL_DRAFT_CREATED"
    EMAIL_DRAFT_EDITED = "EMAIL_DRAFT_EDITED"
    EMAIL_APPROVED = "EMAIL_APPROVED"
    EMAIL_SENT = "EMAIL_SENT"
    EMAIL_SEND_FAILED = "EMAIL_SEND_FAILED"
    EMAIL_CANCELLED = "EMAIL_CANCELLED"
    EMAIL_ACCOUNT_CONNECTED = "EMAIL_ACCOUNT_CONNECTED"
    EMAIL_ACCOUNT_DISCONNECTED = "EMAIL_ACCOUNT_DISCONNECTED"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    APPLICATION_ANSWER_EDITED = "APPLICATION_ANSWER_EDITED"
    APPLICATION_APPROVED = "APPLICATION_APPROVED"
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    APPLICATION_STATUS_CHANGED = "APPLICATION_STATUS_CHANGED"


class AuditLog(UUIDPrimaryKey, Base):
    """Append-only record of user-visible and external actions. Never stores secrets."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor: Mapped[str] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[uuid.UUID | None]
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
