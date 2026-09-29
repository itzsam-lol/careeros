from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from careeros.api.deps import CurrentUser, DbSession
from careeros.core.clock import utcnow
from careeros.core.errors import ConflictError, NotFoundError
from careeros.events.models import EventType
from careeros.events.service import recent_for_user
from careeros.tasks.models import AgentTask, TaskStatus, TaskType

router = APIRouter(tags=["activity"])


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: TaskType
    status: TaskStatus
    payload: dict[str, Any]
    result: dict[str, Any] | None
    error: str | None
    error_type: str | None
    attempt_count: int
    max_attempts: int
    run_after: datetime
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: EventType
    summary: str
    job_id: uuid.UUID | None
    company_id: uuid.UUID | None
    application_id: uuid.UUID | None
    outreach_id: uuid.UUID | None
    payload: dict[str, Any]
    created_at: datetime


async def _own_task(session: Any, user_id: uuid.UUID, task_id: uuid.UUID) -> AgentTask:
    task = (
        await session.execute(
            select(AgentTask).where(AgentTask.id == task_id, AgentTask.user_id == user_id)
        )
    ).scalar_one_or_none()
    if task is None:
        raise NotFoundError("Task not found")
    return task  # type: ignore[no-any-return]


@router.get("/tasks", response_model=list[TaskOut])
async def list_tasks(
    user: CurrentUser,
    session: DbSession,
    status: TaskStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[TaskOut]:
    stmt = select(AgentTask).where(AgentTask.user_id == user.id)
    if status is not None:
        stmt = stmt.where(AgentTask.status == status)
    rows = (
        await session.execute(stmt.order_by(AgentTask.created_at.desc()).limit(limit))
    ).scalars()
    return [TaskOut.model_validate(row) for row in rows]


@router.get("/tasks/{task_id}", response_model=TaskOut)
async def get_task(task_id: uuid.UUID, user: CurrentUser, session: DbSession) -> TaskOut:
    return TaskOut.model_validate(await _own_task(session, user.id, task_id))


@router.post("/tasks/{task_id}/retry", response_model=TaskOut)
async def retry_task(task_id: uuid.UUID, user: CurrentUser, session: DbSession) -> TaskOut:
    task = await _own_task(session, user.id, task_id)
    if task.status not in (TaskStatus.FAILED, TaskStatus.WAITING_FOR_USER, TaskStatus.CANCELLED):
        raise ConflictError("Only failed, waiting or cancelled tasks can be retried")
    task.status = TaskStatus.QUEUED
    task.attempt_count = 0
    task.run_after = utcnow()
    task.error = task.error_type = None
    task.completed_at = None
    await session.commit()
    return TaskOut.model_validate(task)


@router.post("/tasks/{task_id}/cancel", response_model=TaskOut)
async def cancel_task(task_id: uuid.UUID, user: CurrentUser, session: DbSession) -> TaskOut:
    task = await _own_task(session, user.id, task_id)
    if task.status not in (TaskStatus.QUEUED, TaskStatus.WAITING_FOR_USER):
        raise ConflictError("Only queued or waiting tasks can be cancelled")
    task.status = TaskStatus.CANCELLED
    task.completed_at = utcnow()
    await session.commit()
    return TaskOut.model_validate(task)


@router.get("/activity", response_model=list[EventOut], summary="The agent activity feed")
async def activity(
    user: CurrentUser,
    session: DbSession,
    limit: Annotated[int, Query(ge=1, le=300)] = 100,
    job_id: uuid.UUID | None = None,
) -> list[EventOut]:
    events = await recent_for_user(session, user.id, limit=limit, job_id=job_id)
    return [EventOut.model_validate(event) for event in events]
