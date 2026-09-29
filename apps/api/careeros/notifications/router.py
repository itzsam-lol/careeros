from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from careeros.api.deps import CurrentUser, DbSession
from careeros.notifications import service
from careeros.notifications.models import NotificationPriority, NotificationType

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
