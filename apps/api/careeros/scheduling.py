"""The built-in scheduler (runs inside the worker every minute, one instance at a time).

Replaces Cloud Scheduler + Pub/Sub for the single-VM deployment: due sources and periodic
maintenance become queued tasks with time-slot idempotency keys, so a double tick never
duplicates work.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.discovery.models import CADENCE_INTERVALS, DiscoveryCadence, JobSource
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue

if TYPE_CHECKING:
    from careeros.container import Container


async def schedule_due_sources(session: AsyncSession) -> int:
    now = utcnow()
    sources = list(
        (
            await session.execute(
                select(JobSource)
                .where(
                    JobSource.enabled.is_(True),
                    JobSource.cadence != DiscoveryCadence.MANUAL,
                    or_(JobSource.next_run_at.is_(None), JobSource.next_run_at <= now),
                )
                .limit(200)
                .with_for_update(skip_locked=True)
            )
        ).scalars()
    )
    for source in sources:
        interval = CADENCE_INTERVALS[source.cadence]
        if interval is None:
            continue
        slot = int(now.timestamp() // interval.total_seconds())
        await enqueue(
            session,
            TaskType.RUN_DISCOVERY,
            {"source_id": str(source.id)},
            user_id=source.user_id,
            idempotency_key=f"discovery:{source.id}:{slot}",
            priority=1,
        )
        source.next_run_at = now + interval
    return len(sources)


async def tick(session: AsyncSession, container: Container) -> dict[str, int]:
    from careeros.scheduled_jobs import schedule_periodic

    scheduled = {"discovery": await schedule_due_sources(session)}
    scheduled.update(await schedule_periodic(session, container))
    return scheduled
