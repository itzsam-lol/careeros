from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from careeros.api.deps import ContainerDep, CurrentUser, DbSession
from careeros.core.clock import utcnow
from careeros.notifications import service
from careeros.notifications.models import NotificationPriority, NotificationType, PushDevice
from careeros.notifications.push import send_test_push

router = APIRouter(prefix="/notifications", tags=["notifications"])


class NotificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: NotificationType
    priority: NotificationPriority
    title: str
    body: str
    job_id: uuid.UUID | None
    application_id: uuid.UUID | None
    outreach_id: uuid.UUID | None
    action_url: str | None
    data: dict[str, Any]
    read: bool
    pushed_at: datetime | None
    created_at: datetime


class MarkRead(BaseModel):
    ids: Annotated[list[uuid.UUID], Field(max_length=500)] | None = None


class UnreadCount(BaseModel):
    unread: int


@router.get("", response_model=list[NotificationOut])
async def list_notifications(
    user: CurrentUser,
    session: DbSession,
    unread_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[NotificationOut]:
    rows = await service.list_notifications(session, user.id, unread_only=unread_only, limit=limit)
    return [NotificationOut.model_validate(row) for row in rows]


@router.get("/unread-count", response_model=UnreadCount)
async def get_unread_count(user: CurrentUser, session: DbSession) -> UnreadCount:
    return UnreadCount(unread=await service.unread_count(session, user.id))


@router.post("/read", response_model=UnreadCount, summary="Mark some (or all) notifications read")
async def mark_read(payload: MarkRead, user: CurrentUser, session: DbSession) -> UnreadCount:
    await service.mark_read(session, user.id, payload.ids)
    await session.commit()
    return UnreadCount(unread=await service.unread_count(session, user.id))


devices_router = APIRouter(prefix="/devices", tags=["notifications"])


class DeviceIn(BaseModel):
    token: Annotated[str, Field(min_length=20, max_length=4096)]
    platform: Literal["android", "ios"] = "android"


class DeviceTokenIn(BaseModel):
    token: Annotated[str, Field(min_length=20, max_length=4096)]


class PushStatus(BaseModel):
    push_enabled: bool
    devices: int


class PushTest(PushStatus):
    sent: int


async def _push_status(
    session: DbSession, user: CurrentUser, container: ContainerDep
) -> PushStatus:
    count = (
        await session.execute(
            select(func.count()).select_from(PushDevice).where(PushDevice.user_id == user.id)
        )
    ).scalar_one()
    return PushStatus(push_enabled=container.push.enabled, devices=int(count))


@devices_router.get(
    "/status", response_model=PushStatus, summary="Whether alerts are pushed to your phones"
)
async def push_status(user: CurrentUser, session: DbSession, container: ContainerDep) -> PushStatus:
    return await _push_status(session, user, container)


@devices_router.post("", response_model=PushStatus, summary="Register this phone for push alerts")
async def register_device(
    payload: DeviceIn, user: CurrentUser, session: DbSession, container: ContainerDep
) -> PushStatus:
    now = utcnow()
    await session.execute(
        pg_insert(PushDevice)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            token=payload.token,
            platform=payload.platform,
            created_at=now,
            last_seen_at=now,
        )
        # A phone that signs in to another account moves to that account.
        .on_conflict_do_update(
            index_elements=["token"], set_={"user_id": user.id, "last_seen_at": now}
        )
    )
    await session.commit()
    return await _push_status(session, user, container)


@devices_router.post("/unregister", status_code=204, summary="Stop push alerts to this phone")
async def unregister_device(
    payload: DeviceTokenIn, user: CurrentUser, session: DbSession
) -> Response:
    await session.execute(
        delete(PushDevice).where(PushDevice.token == payload.token, PushDevice.user_id == user.id)
    )
    await session.commit()
    return Response(status_code=204)


@devices_router.post(
    "/test", response_model=PushTest, summary="Send a test notification to your phones now"
)
async def test_push(user: CurrentUser, session: DbSession, container: ContainerDep) -> PushTest:
    sent = await send_test_push(session, container.push, user.id)
    await session.commit()
    status = await _push_status(session, user, container)
    return PushTest(push_enabled=status.push_enabled, devices=status.devices, sent=sent)
