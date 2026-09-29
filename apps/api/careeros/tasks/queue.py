"""Enqueueing and claiming tasks.

Enqueue happens inside the caller's transaction (the task commits atomically with the change
that caused it). Idempotency keys make duplicate enqueues no-ops, so event handlers and
schedulers can be retried freely.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.tasks.models import AgentTask, TaskStatus, TaskType


async def enqueue(
    session: AsyncSession,
    task_type: TaskType,
    payload: dict[str, Any],
    *,
    user_id: uuid.UUID | None = None,
    idempotency_key: str | None = None,
    run_after: datetime | None = None,
    priority: int = 0,
    max_attempts: int = 5,
) -> uuid.UUID:
    """Insert a task (no-op if the idempotency key already exists). Returns the task id."""
    now = utcnow()
    task_id = uuid.uuid4()
    insert_stmt = pg_insert(AgentTask).values(
        id=task_id,
        user_id=user_id,
        type=task_type,
        status=TaskStatus.QUEUED,
        payload=payload,
        attempt_count=0,
        max_attempts=max_attempts,
        priority=priority,
        run_after=run_after or now,
        idempotency_key=idempotency_key,
        created_at=now,
        updated_at=now,
    )
    if idempotency_key is not None:
        insert_stmt = insert_stmt.on_conflict_do_nothing(
            index_elements=["idempotency_key"],
            index_where=AgentTask.idempotency_key.is_not(None),
        )
    inserted = (await session.execute(insert_stmt.returning(AgentTask.id))).scalar_one_or_none()
    if inserted is not None:
        return inserted
    existing = (
        await session.execute(
            select(AgentTask.id).where(AgentTask.idempotency_key == idempotency_key)
        )
    ).scalar_one()
    return existing


async def claim_batch(
    session: AsyncSession, *, worker_id: str, limit: int, lease_seconds: int
) -> list[AgentTask]:
    """Atomically claim due tasks (FOR UPDATE SKIP LOCKED) and mark them RUNNING."""
    now = utcnow()
    due = (
        select(AgentTask.id)
        .where(AgentTask.status == TaskStatus.QUEUED, AgentTask.run_after <= now)
        .order_by(AgentTask.priority.desc(), AgentTask.run_after)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    ids = list((await session.execute(due)).scalars())
    if not ids:
        return []
    claimed = await session.execute(
        update(AgentTask)
        .where(AgentTask.id.in_(ids))
        .values(
            status=TaskStatus.RUNNING,
            locked_by=worker_id,
            locked_until=now + timedelta(seconds=lease_seconds),
            started_at=now,
            attempt_count=AgentTask.attempt_count + 1,
            updated_at=now,
        )
        .returning(AgentTask)
        .execution_options(synchronize_session=False)
    )
    return list(claimed.scalars())


async def claim_one(
    session: AsyncSession, task_id: uuid.UUID, *, worker_id: str, lease_seconds: int
) -> AgentTask | None:
    """Claim a specific task if it is due (used for inline execution)."""
    now = utcnow()
    result = await session.execute(
        update(AgentTask)
        .where(
            AgentTask.id == task_id,
            AgentTask.status == TaskStatus.QUEUED,
            AgentTask.run_after <= now,
        )
        .values(
            status=TaskStatus.RUNNING,
            locked_by=worker_id,
            locked_until=now + timedelta(seconds=lease_seconds),
            started_at=now,
            attempt_count=AgentTask.attempt_count + 1,
            updated_at=now,
        )
        .returning(AgentTask)
        .execution_options(synchronize_session=False)
    )
    return result.scalar_one_or_none()


async def recover_stale(session: AsyncSession) -> int:
    """Re-queue RUNNING tasks whose lease expired (worker crashed or was stopped)."""
    now = utcnow()
    result = await session.execute(
        update(AgentTask)
        .where(
            AgentTask.status == TaskStatus.RUNNING,
            or_(AgentTask.locked_until.is_(None), AgentTask.locked_until < now),
        )
        .values(
            status=TaskStatus.QUEUED,
            locked_by=None,
            locked_until=None,
            run_after=now,
            updated_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    return int(getattr(result, "rowcount", 0) or 0)


def backoff_delay(attempt: int, *, base: float = 20.0, cap: float = 3600.0) -> timedelta:
    """Exponential backoff with full jitter: 20s, 40s, 80s ... capped at 1h."""
    ceiling = min(cap, base * 2 ** max(0, attempt - 1))
    return timedelta(seconds=random.uniform(ceiling / 2, ceiling))


async def cancel_pending(session: AsyncSession, *, task_type: TaskType, key_prefix: str) -> int:
    result = await session.execute(
        update(AgentTask)
        .where(
            and_(
                AgentTask.type == task_type,
                AgentTask.status == TaskStatus.QUEUED,
                AgentTask.idempotency_key.startswith(key_prefix),
            )
        )
        .values(status=TaskStatus.CANCELLED, completed_at=utcnow())
        .execution_options(synchronize_session=False)
    )
    return int(getattr(result, "rowcount", 0) or 0)
