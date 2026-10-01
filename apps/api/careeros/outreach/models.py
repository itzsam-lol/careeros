from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from careeros.db.base import Base, Timestamped, UUIDPrimaryKey, enum_type


class EmailAccountStatus(StrEnum):
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"  # the mailbox rejected the stored password (e.g. it was revoked)


class OutreachStatus(StrEnum):
    DRAFT = "DRAFT"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class EmailAccount(UUIDPrimaryKey, Timestamped, Base):
    """The user's own mailbox, used only to send emails they approve and to spot replies."""

    __tablename__ = "email_accounts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(20), default="gmail")
    address: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str | None] = mapped_column(String(200))
    # Fernet-encrypted app password (never returned by the API, never logged).
    secret: Mapped[str] = mapped_column(Text)
    smtp_host: Mapped[str] = mapped_column(String(200))
    smtp_port: Mapped[int]
    imap_host: Mapped[str] = mapped_column(String(200))
    imap_port: Mapped[int]
    status: Mapped[EmailAccountStatus] = mapped_column(
        enum_type(EmailAccountStatus), default=EmailAccountStatus.CONNECTED
    )
    last_error: Mapped[str | None] = mapped_column(Text)
    verified_at: Mapped[datetime | None]
    replies_checked_at: Mapped[datetime | None]


class OutreachMessage(UUIDPrimaryKey, Timestamped, Base):
    """One email the user writes (usually from a draft) and sends only after approving it."""

    __tablename__ = "outreach_messages"
    __table_args__ = (
        Index("ix_outreach_messages_user_created", "user_id", "created_at"),
        Index("ix_outreach_messages_user_job", "user_id", "job_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    job_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))
    kind: Mapped[str] = mapped_column(String(40), default="custom")
    to_address: Mapped[str] = mapped_column(String(320))
    to_name: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    attach_resume: Mapped[bool] = mapped_column(default=False)
    status: Mapped[OutreachStatus] = mapped_column(
        enum_type(OutreachStatus), default=OutreachStatus.DRAFT
    )
    approved_at: Mapped[datetime | None]
    sent_at: Mapped[datetime | None]
    error: Mapped[str | None] = mapped_column(Text)
    # RFC 5322 Message-ID of the sent email; replies reference it.
    message_id: Mapped[str | None] = mapped_column(String(300), index=True)
    attachment_name: Mapped[str | None] = mapped_column(String(200))
    reply_received_at: Mapped[datetime | None]
    reply_from: Mapped[str | None] = mapped_column(String(320))
    reply_snippet: Mapped[str | None] = mapped_column(Text)
