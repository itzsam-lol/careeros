from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response, status
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select

from careeros.api.deps import ContainerDep, CurrentUser, DbSession, rate_limit
from careeros.core.clock import utcnow
from careeros.jobs.models import Job
from careeros.outreach import service
from careeros.outreach.models import EmailAccountStatus, OutreachMessage, OutreachStatus

router = APIRouter(prefix="/email", tags=["email"])

Address = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=320)]
Kind = Literal["referral_request", "follow_up", "thank_you", "custom"]


class EmailAccountOut(BaseModel):
    connected: bool
    address: str | None = None
    display_name: str | None = None
    status: EmailAccountStatus | None = None
    last_error: str | None = None
    verified_at: datetime | None = None
    replies_checked_at: datetime | None = None
    daily_limit: int
    sent_last_24h: int


class ConnectIn(BaseModel):
    address: Address
    app_password: Annotated[str, StringConstraints(min_length=8, max_length=100)]
    display_name: Annotated[str, StringConstraints(max_length=200)] | None = None


class MessageIn(BaseModel):
    job_id: uuid.UUID | None = None
    kind: Kind = "custom"
    to_address: Address
    to_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    subject: Annotated[str, StringConstraints(max_length=300)]
    body: Annotated[str, StringConstraints(max_length=20_000)]
    attach_resume: bool = False


class MessagePatch(BaseModel):
    to_address: Address | None = None
    to_name: Annotated[str, StringConstraints(max_length=200)] | None = None
    subject: Annotated[str, StringConstraints(max_length=300)] | None = None
    body: Annotated[str, StringConstraints(max_length=20_000)] | None = None
    attach_resume: bool | None = None


class SendIn(BaseModel):
    # The client sends this only after the user has reviewed the final email and tapped Send.
    confirm: Literal[True]


class MessageOut(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID | None
    job_title: str | None = None
    company: str | None = None
    kind: str
    to_address: str
    to_name: str | None
    subject: str
    body: str
    attach_resume: bool
    status: OutreachStatus
    approved_at: datetime | None
    sent_at: datetime | None
    error: str | None
    attachment_name: str | None
    reply_received_at: datetime | None
    reply_from: str | None
    reply_snippet: str | None
    created_at: datetime
    updated_at: datetime


class RepliesChecked(BaseModel):
    replies: int


async def _out(session: DbSession, message: OutreachMessage) -> MessageOut:
    job = await session.get(Job, message.job_id) if message.job_id else None
    return MessageOut(
        id=message.id,
        job_id=message.job_id,
        job_title=job.title if job else None,
        company=job.company if job else None,
        kind=message.kind,
        to_address=message.to_address,
        to_name=message.to_name,
        subject=message.subject,
        body=message.body,
        attach_resume=message.attach_resume,
        status=message.status,
        approved_at=message.approved_at,
        sent_at=message.sent_at,
        error=message.error,
        attachment_name=message.attachment_name,
        reply_received_at=message.reply_received_at,
        reply_from=message.reply_from,
        reply_snippet=message.reply_snippet,
        created_at=message.created_at,
        updated_at=message.updated_at,
    )


async def _account_out(
    session: DbSession, user: CurrentUser, container: ContainerDep
) -> EmailAccountOut:
    account = await service.get_account(session, user.id)
    sent = await service.sent_since(session, user.id, utcnow() - service.DAY)
    limit = container.settings.outreach_daily_limit
    if account is None:
        return EmailAccountOut(connected=False, daily_limit=limit, sent_last_24h=sent)
    return EmailAccountOut(
        connected=account.status == EmailAccountStatus.CONNECTED,
        address=account.address,
        display_name=account.display_name,
        status=account.status,
        last_error=account.last_error,
        verified_at=account.verified_at,
        replies_checked_at=account.replies_checked_at,
        daily_limit=limit,
        sent_last_24h=sent,
    )


@router.get("/account", response_model=EmailAccountOut, summary="Your connected mailbox")
async def get_account(
    user: CurrentUser, session: DbSession, container: ContainerDep
) -> EmailAccountOut:
    return await _account_out(session, user, container)


@router.put(
    "/account",
    response_model=EmailAccountOut,
    summary="Connect Gmail with an app password (checked with Gmail before saving)",
    dependencies=[Depends(rate_limit("email.connect", limit=6, window_seconds=600))],
)
async def connect_account(
    payload: ConnectIn, user: CurrentUser, session: DbSession, container: ContainerDep
) -> EmailAccountOut:
    await service.connect_account(
        session,
        user=user,
        address=payload.address,
        app_password=payload.app_password,
        display_name=payload.display_name,
        transport=container.mail,
        cipher=container.cipher,
    )
    await session.commit()
    return await _account_out(session, user, container)


@router.delete(
    "/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Disconnect and forget the app password",
)
async def disconnect_account(user: CurrentUser, session: DbSession) -> Response:
    await service.disconnect_account(session, user)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/messages", response_model=list[MessageOut], summary="Your outreach emails, newest first"
)
async def list_messages(
    user: CurrentUser,
    session: DbSession,
    job_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[MessageOut]:
    stmt = select(OutreachMessage).where(OutreachMessage.user_id == user.id)
    if job_id is not None:
        stmt = stmt.where(OutreachMessage.job_id == job_id)
    rows = (
        await session.execute(stmt.order_by(OutreachMessage.created_at.desc()).limit(limit))
    ).scalars()
    return [await _out(session, message) for message in rows]


@router.post(
    "/messages",
    response_model=MessageOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save a draft email",
)
async def create_message(payload: MessageIn, user: CurrentUser, session: DbSession) -> MessageOut:
    message = await service.create_message(session, user_id=user.id, data=payload.model_dump())
    await session.commit()
    return await _out(session, message)


@router.get("/messages/{message_id}", response_model=MessageOut)
async def get_message(message_id: uuid.UUID, user: CurrentUser, session: DbSession) -> MessageOut:
    return await _out(session, await service.get_message(session, user.id, message_id))


@router.patch("/messages/{message_id}", response_model=MessageOut, summary="Edit a draft")
async def update_message(
    message_id: uuid.UUID, payload: MessagePatch, user: CurrentUser, session: DbSession
) -> MessageOut:
    message = await service.get_message(session, user.id, message_id)
    await service.update_message(session, message, payload.model_dump(exclude_unset=True))
    await session.commit()
    return await _out(session, message)


@router.delete(
    "/messages/{message_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a draft"
)
async def delete_message(message_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    message = await service.get_message(session, user.id, message_id)
    await service.delete_message(session, message)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/messages/{message_id}/send",
    response_model=MessageOut,
    summary="Send one email you have reviewed (explicit approval; never automatic)",
    dependencies=[Depends(rate_limit("email.send", limit=10, window_seconds=600))],
)
async def send_message(
    message_id: uuid.UUID,
    payload: SendIn,
    user: CurrentUser,
    session: DbSession,
    container: ContainerDep,
) -> MessageOut:
    message = await service.send_message(
        session,
        user=user,
        message_id=message_id,
        transport=container.mail,
        cipher=container.cipher,
        settings=container.settings,
    )
    return await _out(session, message)


@router.post(
    "/check-replies",
    response_model=RepliesChecked,
    summary="Look for replies now",
    dependencies=[Depends(rate_limit("email.replies", limit=6, window_seconds=600))],
)
async def check_replies_now(
    user: CurrentUser, session: DbSession, container: ContainerDep
) -> RepliesChecked:
    account = await service.get_account(session, user.id)
    if account is None or account.status != EmailAccountStatus.CONNECTED:
        raise service.EmailNotConnectedError()
    found = await service.check_replies(
        session, account=account, transport=container.mail, cipher=container.cipher
    )
    await session.commit()
    return RepliesChecked(replies=found)
