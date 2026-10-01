from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from careeros.core.clock import utcnow
from careeros.db.base import Base, UUIDPrimaryKey, enum_type


class NotificationType(StrEnum):
    NEW_JOB = "NEW_JOB"
    HIGH_MATCH = "HIGH_MATCH"
    DEADLINE_SOON = "DEADLINE_SOON"
    RESUME_READY = "RESUME_READY"
    APPLICATION_READY = "APPLICATION_READY"
    APPLICATION_NEEDS_INPUT = "APPLICATION_NEEDS_INPUT"
    CONTACT_FOUND = "CONTACT_FOUND"
    OUTREACH_RECOMMENDED = "OUTREACH_RECOMMENDED"
    OUTREACH_APPROVAL_REQUIRED = "OUTREACH_APPROVAL_REQUIRED"
    REPLY_RECEIVED = "REPLY_RECEIVED"
    FOLLOW_UP_DUE = "FOLLOW_UP_DUE"
    INTERVIEW = "INTERVIEW"
    SOURCE_FAILING = "SOURCE_FAILING"


class NotificationPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Notification(UUIDPrimaryKey, Base):
    __tablename__ = "notifications"
    __table_args__ = (
        UniqueConstraint("user_id", "dedupe_key"),
        Index("ix_notifications_user_read_created", "user_id", "read", "created_at"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    type: Mapped[NotificationType] = mapped_column(enum_type(NotificationType))
    priority: Mapped[NotificationPriority] = mapped_column(
        enum_type(NotificationPriority), default=NotificationPriority.NORMAL
    )
    title: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text, default="")
    job_id: Mapped[uuid.UUID | None]
    application_id: Mapped[uuid.UUID | None]
    outreach_id: Mapped[uuid.UUID | None]
    action_url: Mapped[str | None] = mapped_column(String(300))
    dedupe_key: Mapped[str] = mapped_column(String(200))
    data: Mapped[dict[str, Any]] = mapped_column(default=dict)
    read: Mapped[bool] = mapped_column(default=False)
    read_at: Mapped[datetime | None]
    # When a push for it reached FCM; the phone's own background check skips pushed alerts.
    pushed_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())


class PushDevice(UUIDPrimaryKey, Base):
    """A phone that receives push notifications (an FCM registration token)."""

    __tablename__ = "push_devices"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(Text, unique=True)
    platform: Mapped[str] = mapped_column(String(20), default="android")
    created_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(default=utcnow, server_default=func.now())
