"""Outreach emails the user approves one by one, sent from their own mailbox.

Rules (AUTO_SEND_EMAILS stays off):
- nothing is sent without an explicit "send" on that exact message;
- a daily limit and a duplicate guard protect the user's sender reputation;
- the app password is encrypted at rest and never returned or logged;
- every connect, draft, approval, send and failure is audit-logged.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.audit.models import AuditAction
from careeros.audit.service import record
from careeros.config import Settings
from careeros.core.clock import utcnow
from careeros.core.crypto import TokenCipher
from careeros.core.errors import (
    CareerOSError,
    ConflictError,
    EmailProviderError,
    NotFoundError,
    RateLimitedError,
    ValidationFailedError,
)
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.jobs.models import Job, UserJob
from careeros.notifications.models import NotificationPriority, NotificationType
from careeros.notifications.service import notify
from careeros.outreach.mailer import (
    GMAIL,
    EmailLoginError,
    Mailbox,
    MailServer,
    MailTransport,
    build_email,
)
from careeros.outreach.models import (
    EmailAccount,
    EmailAccountStatus,
    OutreachMessage,
    OutreachStatus,
)
from careeros.profile.models import ProfessionalProfile
from careeros.resumes.models import DocumentKind, DocumentStatus, ResumeDocument
from careeros.resumes.service import pdf_filename
from careeros.users.models import User

DAY = timedelta(hours=24)
REPLY_WINDOW = timedelta(days=30)
STALE_SENDING = timedelta(minutes=10)
KINDS = ("referral_request", "follow_up", "thank_you", "custom")
_EMAIL = re.compile(r"^[^@\s<>,;:\"'()\[\]]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")
_LINE_BREAK = re.compile(r"[\r\n]+")


class EmailNotConnectedError(CareerOSError):
    """Connect your Gmail in Settings > Email before sending."""

    code = "email_not_connected"
    http_status = 409


def _clean_address(value: str) -> str:
    address = value.strip()
    if not _EMAIL.match(address):
        raise ValidationFailedError(f"'{address[:80]}' is not a valid email address")
    return address


def _one_line(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    return _LINE_BREAK.sub(" ", value).strip()[:limit] or None


def mailbox_for(account: EmailAccount, cipher: TokenCipher) -> Mailbox:
    server = MailServer(account.smtp_host, account.smtp_port, account.imap_host, account.imap_port)
    return Mailbox(server, account.address, cipher.decrypt(account.secret))


async def get_account(session: AsyncSession, user_id: uuid.UUID) -> EmailAccount | None:
    return (
        await session.execute(select(EmailAccount).where(EmailAccount.user_id == user_id))
    ).scalar_one_or_none()


async def sent_since(session: AsyncSession, user_id: uuid.UUID, since: datetime) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(OutreachMessage)
                .where(
                    OutreachMessage.user_id == user_id,
                    OutreachMessage.status == OutreachStatus.SENT,
                    OutreachMessage.sent_at >= since,
                )
            )
        ).scalar_one()
    )


async def connect_account(
    session: AsyncSession,
    *,
    user: User,
    address: str,
    app_password: str,
    display_name: str | None,
    transport: MailTransport,
    cipher: TokenCipher,
) -> EmailAccount:
    address = _clean_address(address).lower()
    password = "".join(app_password.split())  # Google shows app passwords in groups of four
    if len(password) < 8:
        raise ValidationFailedError("That doesn't look like an app password (16 letters)")
    await transport.verify(Mailbox(GMAIL, address, password))
    account = await get_account(session, user.id)
    if account is None:
        account = EmailAccount(user_id=user.id, address=address, secret="")
        session.add(account)
    account.provider = "gmail"
    account.address = address
    account.display_name = _one_line(display_name, 200)
    account.secret = cipher.encrypt(password)
    account.smtp_host, account.smtp_port = GMAIL.smtp_host, GMAIL.smtp_port
    account.imap_host, account.imap_port = GMAIL.imap_host, GMAIL.imap_port
    account.status = EmailAccountStatus.CONNECTED
    account.last_error = None
    account.verified_at = utcnow()
    await session.flush()
    await record(
        session,
        action=AuditAction.EMAIL_ACCOUNT_CONNECTED,
        user_id=user.id,
        entity_type="email_account",
        entity_id=account.id,
        metadata={"address": address, "provider": "gmail"},
    )
    return account


async def disconnect_account(session: AsyncSession, user: User) -> None:
    account = await get_account(session, user.id)
    if account is None:
        return
    await record(
        session,
        action=AuditAction.EMAIL_ACCOUNT_DISCONNECTED,
        user_id=user.id,
        entity_type="email_account",
        entity_id=account.id,
        metadata={"address": account.address},
    )
    await session.delete(account)
    await session.flush()


async def _owned_job(session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> Job:
    job = (
        await session.execute(
            select(Job)
            .join(UserJob, UserJob.job_id == Job.id)
            .where(Job.id == job_id, UserJob.user_id == user_id)
        )
    ).scalar_one_or_none()
    if job is None:
        raise NotFoundError("Job not found")
    return job


async def get_message(
    session: AsyncSession, user_id: uuid.UUID, message_id: uuid.UUID
) -> OutreachMessage:
    message = await session.get(OutreachMessage, message_id)
    if message is None or message.user_id != user_id:
        raise NotFoundError("Email not found")
    return message


def _apply_fields(message: OutreachMessage, data: dict[str, Any]) -> None:
    if "to_address" in data and data["to_address"] is not None:
        message.to_address = _clean_address(data["to_address"])
    if "to_name" in data:
        message.to_name = _one_line(data["to_name"], 200)
    if "subject" in data and data["subject"] is not None:
        subject = _one_line(data["subject"], 300)
        if not subject:
            raise ValidationFailedError("The subject can't be empty")
        message.subject = subject
    if "body" in data and data["body"] is not None:
        body = str(data["body"]).strip()
        if not body:
            raise ValidationFailedError("The email can't be empty")
        if len(body) > 20_000:
            raise ValidationFailedError("The email is too long (20,000 characters at most)")
        message.body = body
    if "attach_resume" in data and data["attach_resume"] is not None:
        message.attach_resume = bool(data["attach_resume"])


async def create_message(
    session: AsyncSession, *, user_id: uuid.UUID, data: dict[str, Any]
) -> OutreachMessage:
    job_id = data.get("job_id")
    if job_id is not None:
        await _owned_job(session, user_id, job_id)
    kind = data.get("kind") or "custom"
    if kind not in KINDS:
        raise ValidationFailedError(f"Unknown email kind '{kind}'")
    message = OutreachMessage(
        user_id=user_id, job_id=job_id, kind=kind, to_address="", subject="", body=""
    )
    _apply_fields(message, {"attach_resume": False, **data})
    if not message.to_address or not message.subject or not message.body:
        raise ValidationFailedError("An email needs a recipient, a subject and a message")
    session.add(message)
    await session.flush()
    await record(
        session,
        action=AuditAction.EMAIL_DRAFT_CREATED,
        user_id=user_id,
        entity_type="outreach_message",
        entity_id=message.id,
        metadata={"kind": kind, "job_id": str(job_id) if job_id else None},
    )
    return message


def _editable(message: OutreachMessage) -> None:
    if message.status not in (OutreachStatus.DRAFT, OutreachStatus.FAILED):
        raise ConflictError("This email has already been sent")


async def update_message(
    session: AsyncSession, message: OutreachMessage, data: dict[str, Any]
) -> OutreachMessage:
    _editable(message)
    _apply_fields(message, data)
    if message.status == OutreachStatus.FAILED:
        message.status = OutreachStatus.DRAFT  # edited after a failure: back to a draft
    await session.flush()
    await record(
        session,
        action=AuditAction.EMAIL_DRAFT_EDITED,
        user_id=message.user_id,
        entity_type="outreach_message",
        entity_id=message.id,
        metadata={"fields": sorted(data)},
    )
    return message


async def delete_message(session: AsyncSession, message: OutreachMessage) -> None:
    _editable(message)
    await record(
        session,
        action=AuditAction.EMAIL_CANCELLED,
        user_id=message.user_id,
        entity_type="outreach_message",
        entity_id=message.id,
    )
    await session.delete(message)
    await session.flush()


async def _resume_attachment(
    session: AsyncSession, message: OutreachMessage
) -> tuple[str, bytes] | None:
    if not message.attach_resume:
        return None
    if message.job_id is None:
        raise ValidationFailedError("Résumés can only be attached to emails about a job")
    document = (
        await session.execute(
            select(ResumeDocument)
            .where(
                ResumeDocument.user_id == message.user_id,
                ResumeDocument.job_id == message.job_id,
                ResumeDocument.kind == DocumentKind.RESUME,
                ResumeDocument.status == DocumentStatus.READY,
                ResumeDocument.pdf.is_not(None),
            )
            .order_by(ResumeDocument.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if document is None or document.pdf is None:
        raise ValidationFailedError(
            "There is no tailored résumé for this job yet. Create one, or turn off the attachment."
        )
    full_name = (
        await session.execute(
            select(ProfessionalProfile.full_name).where(
                ProfessionalProfile.user_id == message.user_id
            )
        )
    ).scalar_one_or_none()
    return pdf_filename(document, full_name), document.pdf


async def send_message(
    session: AsyncSession,
    *,
    user: User,
    message_id: uuid.UUID,
    transport: MailTransport,
    cipher: TokenCipher,
    settings: Settings,
) -> OutreachMessage:
    """Send one email the user has just approved. Commits before and after talking to Gmail."""
    message = (
        await session.execute(
            select(OutreachMessage)
            .where(OutreachMessage.id == message_id, OutreachMessage.user_id == user.id)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if message is None:
        raise NotFoundError("Email not found")
    now = utcnow()
    if message.status == OutreachStatus.SENT:
        raise ConflictError("This email has already been sent")
    if message.status == OutreachStatus.SENDING and now - message.updated_at < STALE_SENDING:
        raise ConflictError("This email is being sent")
    account = await get_account(session, user.id)
    if account is None:
        raise EmailNotConnectedError()
    if account.status != EmailAccountStatus.CONNECTED:
        raise EmailNotConnectedError(
            "Gmail stopped accepting the saved app password. Reconnect it in Settings > Email."
        )
    if await sent_since(session, user.id, now - DAY) >= settings.outreach_daily_limit:
        raise RateLimitedError(
            f"You've sent {settings.outreach_daily_limit} emails in the last 24 hours, the daily "
            "limit that keeps your address out of spam folders. Try again later."
        )
    duplicate = (
        await session.execute(
            select(OutreachMessage.id).where(
                OutreachMessage.user_id == user.id,
                OutreachMessage.id != message.id,
                OutreachMessage.status == OutreachStatus.SENT,
                func.lower(OutreachMessage.to_address) == message.to_address.lower(),
                OutreachMessage.subject == message.subject,
                OutreachMessage.sent_at >= now - DAY,
            )
        )
    ).first()
    if duplicate:
        raise ConflictError("You sent this same email to this person in the last 24 hours")
    attachment = await _resume_attachment(session, message)
    mailbox = mailbox_for(account, cipher)

    message.status = OutreachStatus.SENDING
    message.approved_at = now
    message.error = None
    await record(
        session,
        action=AuditAction.EMAIL_APPROVED,
        user_id=user.id,
        entity_type="outreach_message",
        entity_id=message.id,
        metadata={
            "to": message.to_address,
            "subject": message.subject,
            "attachment": bool(attachment),
        },
    )
    await session.commit()  # a crash mid-send must not lead to a silent second send

    outgoing = build_email(
        sender=account.address,
        sender_name=account.display_name,
        to=message.to_address,
        to_name=message.to_name,
        subject=message.subject,
        body=message.body,
        attachment=attachment,
    )
    try:
        await transport.send(mailbox, outgoing)
    except EmailProviderError as exc:
        if isinstance(exc, EmailLoginError):
            account.status = EmailAccountStatus.ERROR
            account.last_error = exc.message
        message.status = OutreachStatus.FAILED
        message.error = exc.message
        await record(
            session,
            action=AuditAction.EMAIL_SEND_FAILED,
            user_id=user.id,
            entity_type="outreach_message",
            entity_id=message.id,
            metadata={"error": exc.message[:300]},
        )
        await session.commit()
        raise

    message.status = OutreachStatus.SENT
    message.sent_at = utcnow()
    message.message_id = str(outgoing["Message-ID"])
    message.attachment_name = attachment[0] if attachment else None
    await record(
        session,
        action=AuditAction.EMAIL_SENT,
        user_id=user.id,
        entity_type="outreach_message",
        entity_id=message.id,
        metadata={"to": message.to_address, "kind": message.kind},
    )
    await emit(
        session,
        EventType.OUTREACH_SENT,
        user_id=user.id,
        job_id=message.job_id,
        outreach_id=message.id,
        summary=f"Emailed {message.to_name or message.to_address}: {message.subject}",
        payload={"kind": message.kind},
    )
    await session.commit()
    return message


async def check_replies(
    session: AsyncSession,
    *,
    account: EmailAccount,
    transport: MailTransport,
    cipher: TokenCipher,
) -> int:
    """Look for replies to sent emails; alert the user about each new one."""
    now = utcnow()
    waiting = list(
        (
            await session.execute(
                select(OutreachMessage).where(
                    OutreachMessage.user_id == account.user_id,
                    OutreachMessage.status == OutreachStatus.SENT,
                    OutreachMessage.reply_received_at.is_(None),
                    OutreachMessage.message_id.is_not(None),
                    OutreachMessage.sent_at >= now - REPLY_WINDOW,
                )
            )
        ).scalars()
    )
    account.replies_checked_at = now
    if not waiting:
        return 0
    since = min(m.sent_at or now for m in waiting).date()
    try:
        replies = await transport.find_replies(
            mailbox_for(account, cipher), [m.message_id for m in waiting if m.message_id], since
        )
    except EmailLoginError as exc:
        account.status = EmailAccountStatus.ERROR
        account.last_error = exc.message
        return 0
    except EmailProviderError:
        return 0  # transient; the next check retries
    by_id = {m.message_id: m for m in waiting}
    found = 0
    for reply in replies:
        message = by_id.get(reply.in_reply_to)
        if message is None or message.reply_received_at is not None:
            continue
        message.reply_received_at = reply.received_at or now
        message.reply_from = reply.sender[:320]
        message.reply_snippet = reply.snippet
        who = message.to_name or message.to_address
        await notify(
            session,
            user_id=message.user_id,
            type=NotificationType.REPLY_RECEIVED,
            priority=NotificationPriority.HIGH,
            title=f"{who} replied: {message.subject}"[:300],
            body=reply.snippet[:280] or "Open Gmail to read the reply.",
            job_id=message.job_id,
            outreach_id=message.id,
            dedupe_key=f"reply:{message.id}",
            data={"outreach_id": str(message.id)},
        )
        await emit(
            session,
            EventType.OUTREACH_REPLY_DETECTED,
            user_id=message.user_id,
            job_id=message.job_id,
            outreach_id=message.id,
            summary=f"{who} replied to “{message.subject}”",
        )
        found += 1
    return found
