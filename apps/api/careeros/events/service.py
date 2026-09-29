"""Emitting domain events and reacting to them within the same transaction."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.events.models import DomainEvent, EventType

Subscriber = Callable[[AsyncSession, DomainEvent], Awaitable[None]]
_SUBSCRIBERS: dict[EventType, list[Subscriber]] = defaultdict(list)


def subscribe(*event_types: EventType) -> Callable[[Subscriber], Subscriber]:
    def register(fn: Subscriber) -> Subscriber:
        for event_type in event_types:
            if fn not in _SUBSCRIBERS[event_type]:
                _SUBSCRIBERS[event_type].append(fn)
        return fn

    return register


async def emit(
    session: AsyncSession,
    event_type: EventType,
    *,
    summary: str,
    user_id: uuid.UUID | None = None,
    job_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    outreach_id: uuid.UUID | None = None,
    payload: dict[str, Any] | None = None,
) -> DomainEvent:
    """Record an event and run subscribers (which may enqueue tasks) in the same unit of work."""
    raw_task_id = structlog.contextvars.get_contextvars().get("task_id")
    event = DomainEvent(
        type=event_type,
        user_id=user_id,
        job_id=job_id,
        company_id=company_id,
        application_id=application_id,
        outreach_id=outreach_id,
        task_id=uuid.UUID(raw_task_id) if raw_task_id else None,
        summary=summary[:500],
        payload=payload or {},
    )
    session.add(event)
    for subscriber in _SUBSCRIBERS.get(event_type, []):
        await subscriber(session, event)
    return event


async def recent_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    job_id: uuid.UUID | None = None,
    application_id: uuid.UUID | None = None,
    outreach_id: uuid.UUID | None = None,
) -> list[DomainEvent]:
    stmt = select(DomainEvent).where(DomainEvent.user_id == user_id)
    if job_id is not None:
        stmt = stmt.where(DomainEvent.job_id == job_id)
    if application_id is not None:
        stmt = stmt.where(DomainEvent.application_id == application_id)
    if outreach_id is not None:
        stmt = stmt.where(DomainEvent.outreach_id == outreach_id)
    stmt = stmt.order_by(DomainEvent.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars())
