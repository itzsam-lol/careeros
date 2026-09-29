from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, status
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, StringConstraints, computed_field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.api.deps import ContainerDep, CurrentUser, DbSession, rate_limit
from careeros.audit import service as audit
from careeros.audit.models import AuditAction
from careeros.core.clock import utcnow
from careeros.core.errors import ConflictError, NotFoundError
from careeros.discovery.adapters import validate_config
from careeros.discovery.models import DiscoveryCadence, JobSource, SourceType
from careeros.discovery.service import schedule_next
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue

router = APIRouter(prefix="/sources", tags=["sources"])

SourceName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: SourceName
    type: SourceType
    config: dict[str, Any]
    cadence: DiscoveryCadence = DiscoveryCadence.DAILY
    enabled: bool = True


class SourceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: SourceName | None = None
    config: dict[str, Any] | None = None
    cadence: DiscoveryCadence | None = None
    enabled: bool | None = None


class SourceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    type: SourceType
    config: dict[str, Any]
    enabled: bool
    cadence: DiscoveryCadence
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    last_failure_at: datetime | None
    last_error: str | None
    last_jobs_found: int
    total_jobs_found: int
    run_count: int
    error_count: int
    consecutive_failures: int
    avg_duration_ms: float | None
    created_at: datetime

    @computed_field  # type: ignore[prop-decorator]
    @property
    def health(self) -> Literal["disabled", "never_run", "healthy", "degraded", "failing"]:
        if not self.enabled:
            return "disabled"
        if self.run_count == 0:
            return "never_run"
        if self.consecutive_failures >= 3:
            return "failing"
        if self.consecutive_failures > 0:
            return "degraded"
        return "healthy"


class RunQueued(BaseModel):
    task_id: uuid.UUID


async def _get_source(session: AsyncSession, user_id: uuid.UUID, source_id: uuid.UUID) -> JobSource:
    source = (
        await session.execute(
            select(JobSource).where(JobSource.id == source_id, JobSource.user_id == user_id)
        )
    ).scalar_one_or_none()
    if source is None:
        raise NotFoundError("Job source not found")
    return source


async def _ensure_unique(
    session: AsyncSession, user_id: uuid.UUID, identity: str, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(JobSource.id).where(JobSource.user_id == user_id, JobSource.identity == identity)
    if exclude is not None:
        stmt = stmt.where(JobSource.id != exclude)
    if (await session.execute(stmt)).first() is not None:
        raise ConflictError("You already have this source")


@router.get("", response_model=list[SourceOut])
async def list_sources(user: CurrentUser, session: DbSession) -> list[SourceOut]:
    rows = (
        await session.execute(
            select(JobSource).where(JobSource.user_id == user.id).order_by(JobSource.created_at)
        )
    ).scalars()
    return [SourceOut.model_validate(row) for row in rows]


@router.post("", response_model=SourceOut, status_code=status.HTTP_201_CREATED)
async def create_source(
    payload: SourceIn, user: CurrentUser, session: DbSession, container: ContainerDep
) -> SourceOut:
    config, identity = validate_config(payload.type, payload.config, container.settings)
    await _ensure_unique(session, user.id, identity)
    source = JobSource(
        user_id=user.id,
        name=payload.name,
        type=payload.type,
        config=config,
        identity=identity,
        enabled=payload.enabled,
        cadence=payload.cadence,
    )
    session.add(source)
    await session.flush()
    schedule_next(source, utcnow())
    if payload.enabled:
        # Run once right away so the inbox fills without waiting for the cadence.
        await enqueue(
            session,
            TaskType.RUN_DISCOVERY,
            {"source_id": str(source.id)},
            user_id=user.id,
            idempotency_key=f"discovery:{source.id}:initial",
            priority=2,
        )
    await audit.record(
        session,
        action=AuditAction.SOURCE_CREATED,
        user_id=user.id,
        entity_type="job_source",
        entity_id=source.id,
        metadata={"type": payload.type.value},
    )
    await session.commit()
    return SourceOut.model_validate(source)


@router.patch("/{source_id}", response_model=SourceOut)
async def update_source(
    source_id: uuid.UUID,
    payload: SourceUpdate,
    user: CurrentUser,
    session: DbSession,
    container: ContainerDep,
) -> SourceOut:
    source = await _get_source(session, user.id, source_id)
    if payload.config is not None:
        config, identity = validate_config(source.type, payload.config, container.settings)
        await _ensure_unique(session, user.id, identity, exclude=source.id)
        source.config, source.identity = config, identity
    if payload.name is not None:
        source.name = payload.name
    if payload.enabled is not None:
        source.enabled = payload.enabled
    if payload.cadence is not None:
        source.cadence = payload.cadence
        schedule_next(source, utcnow())
    await audit.record(
        session,
        action=AuditAction.SOURCE_UPDATED,
        user_id=user.id,
        entity_type="job_source",
        entity_id=source.id,
        metadata={"fields": sorted(payload.model_fields_set)},
    )
    await session.commit()
    return SourceOut.model_validate(source)


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_source(source_id: uuid.UUID, user: CurrentUser, session: DbSession) -> Response:
    source = await _get_source(session, user.id, source_id)
    await session.delete(source)
    await audit.record(
        session,
        action=AuditAction.SOURCE_DELETED,
        user_id=user.id,
        entity_type="job_source",
        entity_id=source_id,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{source_id}/run", response_model=RunQueued, status_code=status.HTTP_202_ACCEPTED)
async def run_source_now(
    source_id: uuid.UUID,
    user: CurrentUser,
    session: DbSession,
    _: Annotated[None, Depends(rate_limit("sources.run", limit=20, window_seconds=300))],
) -> RunQueued:
    source = await _get_source(session, user.id, source_id)
    minute = int(utcnow().timestamp() // 60)
    task_id = await enqueue(
        session,
        TaskType.RUN_DISCOVERY,
        {"source_id": str(source.id)},
        user_id=user.id,
        idempotency_key=f"discovery:{source.id}:manual:{minute}",
        priority=3,
    )
    await audit.record(
        session,
        action=AuditAction.DISCOVERY_TRIGGERED,
        user_id=user.id,
        entity_type="job_source",
        entity_id=source.id,
    )
    await session.commit()
    return RunQueued(task_id=task_id)
