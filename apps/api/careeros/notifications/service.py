from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.notifications.models import Notification, NotificationPriority, NotificationType


async def notify(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: NotificationType,
    title: str,
    body: str = "",
    dedupe_key: str,
    priority: NotificationPriority = NotificationPriority.NORMAL,
    job_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    outreach_id: uuid.UUID | None = None,
    action_url: str | None = None,
    data: dict[str, Any] | None = None,
) -> bool:
    """Create a notification unless one with the same dedupe key exists. Returns True if new."""
    inserted = (
        await session.execute(
            pg_insert(Notification)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                type=type,
                priority=priority,
                title=title[:300],
                body=body[:4000],
                job_id=job_id,
                application_id=application_id,
                outreach_id=outreach_id,
                action_url=action_url,
                dedupe_key=dedupe_key[:200],
                data=data or {},
                read=False,
                created_at=utcnow(),
            )
            .on_conflict_do_nothing(index_elements=["user_id", "dedupe_key"])
            .returning(Notification.id)
        )
    ).scalar_one_or_none()
    if inserted is None:
        return False
    await emit(
        session,
        EventType.NOTIFICATION_CREATED,
        user_id=user_id,
        job_id=job_id,
        application_id=application_id,
        outreach_id=outreach_id,
        summary=f"Notification: {title[:200]}",
        payload={"notification_id": str(inserted), "type": type.value},
    )
    return True


async def list_notifications(
    session: AsyncSession, user_id: uuid.UUID, *, unread_only: bool = False, limit: int = 50
) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars())


async def unread_count(session: AsyncSession, user_id: uuid.UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == user_id, Notification.read.is_(False))
            )
        ).scalar_one()
    )


async def mark_read(
    session: AsyncSession, user_id: uuid.UUID, notification_ids: list[uuid.UUID] | None = None
) -> int:
    stmt = (
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read.is_(False))
        .values(read=True, read_at=utcnow())
    )
    if notification_ids is not None:
        stmt = stmt.where(Notification.id.in_(notification_ids))
    result = await session.execute(stmt)
    return int(getattr(result, "rowcount", 0) or 0)
