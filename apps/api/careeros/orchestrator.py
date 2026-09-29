"""CareerOrchestrator: maps domain events to follow-up tasks (spec §44).

Agents stay small and explicit; this module is the only place that decides "when X happens,
do Y next". Everything here runs inside the transaction that emitted the event.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.events.models import DomainEvent, EventType
from careeros.events.service import subscribe
from careeros.jobs.models import AnalysisStatus, Job, JobLifecycle, UserJob
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue


async def request_analysis(session: AsyncSession, job: Job) -> None:
    await enqueue(
        session,
        TaskType.ANALYZE_JOB,
        {"job_id": str(job.id)},
        idempotency_key=f"analyze:{job.id}:{job.description_hash[:20]}",
        priority=5,
    )


async def request_match(session: AsyncSession, *, user_id: uuid.UUID, job: Job) -> None:
    await enqueue(
        session,
        TaskType.MATCH_JOB,
        {"job_id": str(job.id), "user_id": str(user_id)},
        user_id=user_id,
        idempotency_key=f"match:{user_id}:{job.id}:{job.description_hash[:20]}",
        priority=4,
    )


@subscribe(EventType.JOB_DISCOVERED, EventType.JOB_NORMALIZED)
async def _on_job_discovered(session: AsyncSession, event: DomainEvent) -> None:
    if event.job_id is None:
        return
    job = await session.get(Job, event.job_id)
    if job is None:
        return
    if (
        job.analysis_status == AnalysisStatus.ANALYZED
        and event.type == EventType.JOB_DISCOVERED
        and event.user_id is not None
    ):
        await request_match(session, user_id=event.user_id, job=job)
    else:
        await request_analysis(session, job)


@subscribe(EventType.JOB_ANALYZED)
async def _on_job_analyzed(session: AsyncSession, event: DomainEvent) -> None:
    if event.job_id is None:
        return
    job = await session.get(Job, event.job_id)
    if job is None:
        return
    user_ids = (
        await session.execute(
            select(UserJob.user_id).where(
                UserJob.job_id == job.id, UserJob.status != JobLifecycle.DISMISSED
            )
        )
    ).scalars()
    for user_id in user_ids:
        await request_match(session, user_id=user_id, job=job)
