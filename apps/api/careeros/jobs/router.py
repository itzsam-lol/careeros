from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from careeros.api.deps import CurrentUser, DbSession, rate_limit
from careeros.core.clock import utcnow
from careeros.core.errors import ConflictError, NotFoundError
from careeros.jobs import service
from careeros.jobs.models import ApplicationStage, JobLifecycle, UserJob
from careeros.jobs.schemas import (
    ApplicationOut,
    ApplicationUpdate,
    DismissRequest,
    JobDetail,
    JobList,
    JobSort,
    JobView,
    NoteRequest,
    StageEvent,
)
from careeros.matching.models import JobMatch
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue
from careeros.users.service import read_settings

router = APIRouter(prefix="/jobs", tags=["jobs"])
FOLLOW_UP_AFTER = timedelta(days=7)


@router.get("", response_model=JobList, summary="Your opportunity inbox")
async def list_jobs(
    user: CurrentUser,
    session: DbSession,
    view: JobView = JobView.ALL,
    sort: JobSort = JobSort.SCORE,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> JobList:
    settings = read_settings(user)
    items, total = await service.list_jobs(
        session,
        user.id,
        view=view,
        sort=sort,
        query=q,
        limit=limit,
        offset=offset,
        high_threshold=settings.matching.high_match_threshold,
    )
    return JobList(items=items, total=total)


@router.get("/{job_id}", response_model=JobDetail)
async def get_job(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> JobDetail:
    return await service.job_detail(session, user.id, job_id)


@router.post("/{job_id}/save", response_model=JobDetail)
async def save_job(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> JobDetail:
    user_job = await service.get_user_job(session, user.id, job_id)
    user_job.status = JobLifecycle.SAVED
    user_job.saved_at = utcnow()
    user_job.dismissed_at = None
    await session.commit()
    return await service.job_detail(session, user.id, job_id)


@router.post("/{job_id}/dismiss", response_model=JobDetail)
async def dismiss_job(
    job_id: uuid.UUID, payload: DismissRequest, user: CurrentUser, session: DbSession
) -> JobDetail:
    user_job = await service.get_user_job(session, user.id, job_id)
    user_job.status = JobLifecycle.DISMISSED
    user_job.dismissed_at = utcnow()
    user_job.dismiss_reason = payload.reason
    await session.commit()
    return await service.job_detail(session, user.id, job_id)


@router.post("/{job_id}/restore", response_model=JobDetail)
async def restore_job(job_id: uuid.UUID, user: CurrentUser, session: DbSession) -> JobDetail:
    user_job = await service.get_user_job(session, user.id, job_id)
    if user_job.status not in (JobLifecycle.DISMISSED, JobLifecycle.SAVED):
        raise ConflictError("Only saved or dismissed jobs can be restored")
    has_match = (
        await session.execute(
            select(JobMatch.id).where(JobMatch.user_id == user.id, JobMatch.job_id == job_id)
        )
    ).first()
    user_job.status = JobLifecycle.MATCHED if has_match else JobLifecycle.DISCOVERED
    user_job.dismissed_at = user_job.saved_at = None
    user_job.dismiss_reason = None
    await session.commit()
    return await service.job_detail(session, user.id, job_id)


@router.put("/{job_id}/note", response_model=JobDetail)
async def set_note(
    job_id: uuid.UUID, payload: NoteRequest, user: CurrentUser, session: DbSession
) -> JobDetail:
    user_job = await service.get_user_job(session, user.id, job_id)
    user_job.note = payload.note
    await session.commit()
    return await service.job_detail(session, user.id, job_id)


@router.post("/{job_id}/rematch", status_code=202)
async def rematch_job(
    job_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    _: Annotated[None, Depends(rate_limit("jobs.rematch", limit=30, window_seconds=300))],
) -> dict[str, str]:
    await service.get_user_job(session, user.id, job_id)
    minute = int(utcnow().timestamp() // 60)
    task_id = await enqueue(
        session,
        TaskType.MATCH_JOB,
        {"job_id": str(job_id), "user_id": str(user.id)},
        user_id=user.id,
        idempotency_key=f"match:{user.id}:{job_id}:manual:{minute}",
        priority=6,
    )
    await session.commit()
    return {"task_id": str(task_id)}


async def _user_job(session: DbSession, user_id: uuid.UUID, job_id: uuid.UUID) -> UserJob:
    user_job = (
        await session.execute(
            select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == job_id)
        )
    ).scalar_one_or_none()
    if user_job is None:
        raise NotFoundError("Job not found")
    return user_job


def _application_out(user_job: UserJob) -> ApplicationOut:
    return ApplicationOut(
        job_id=user_job.job_id,
        stage=user_job.application_stage,
        applied_at=user_job.applied_at,
        follow_up_at=user_job.follow_up_at,
        note=user_job.note,
        history=[StageEvent(**event) for event in user_job.stage_history or []],
    )


@router.get(
    "/{job_id}/application",
    response_model=ApplicationOut,
    summary="Your application status for this job",
)
async def get_application(
    job_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> ApplicationOut:
    return _application_out(await _user_job(session, user.id, job_id))


@router.patch(
    "/{job_id}/application",
    response_model=ApplicationOut,
    summary="Track where your application stands",
)
async def update_application(
    job_id: uuid.UUID, payload: ApplicationUpdate, user: CurrentUser, session: DbSession
) -> ApplicationOut:
    user_job = await _user_job(session, user.id, job_id)
    now = utcnow()
    if "stage" in payload.model_fields_set and payload.stage != user_job.application_stage:
        user_job.application_stage = payload.stage
        user_job.stage_changed_at = now
        user_job.stage_history = [
            *(user_job.stage_history or []),
            {"stage": payload.stage.value if payload.stage else None, "at": now.isoformat()},
        ]
        if payload.stage == ApplicationStage.APPLIED:
            user_job.applied_at = user_job.applied_at or now
            # A gentle default nudge a week later, unless the user sets their own.
            if user_job.follow_up_at is None and payload.follow_up_at is None:
                user_job.follow_up_at = now + FOLLOW_UP_AFTER
        if payload.stage in (ApplicationStage.OFFER, ApplicationStage.ACCEPTED, ApplicationStage.REJECTED,
                             ApplicationStage.WITHDRAWN, None):  # fmt: skip
            user_job.follow_up_at = None
        if payload.stage is not None and user_job.status in (JobLifecycle.DISCOVERED, JobLifecycle.ANALYZED,
                                                             JobLifecycle.MATCHED, JobLifecycle.NOTIFIED):  # fmt: skip
            user_job.status = JobLifecycle.SAVED
            user_job.saved_at = user_job.saved_at or now
    if payload.applied_at is not None:
        user_job.applied_at = payload.applied_at
    if payload.follow_up_at is not None:
        user_job.follow_up_at = payload.follow_up_at
    if payload.clear_follow_up:
        user_job.follow_up_at = None
    if payload.note is not None:
        user_job.note = payload.note or None
    await session.commit()
    return _application_out(user_job)
