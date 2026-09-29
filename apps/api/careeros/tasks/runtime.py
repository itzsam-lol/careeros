"""Task execution: handler registry, retry policy and the worker loop."""

from __future__ import annotations

import asyncio
import contextlib
import os
import socket
import time
import traceback
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.core.errors import (
    AuthenticationRequiredError,
    CaptchaDetectedError,
    CareerOSError,
)
from careeros.core.logging import bound_context, get_logger
from careeros.tasks import queue
from careeros.tasks.models import AgentTask, TaskStatus, TaskType

if TYPE_CHECKING:
    from careeros.container import Container

log = get_logger(__name__)

SessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


class WaitingForUserError(CareerOSError):
    """The task needs the user to act before it can continue."""

    code = "waiting_for_user"
    http_status = 409


_WAITING_ERRORS: tuple[type[CareerOSError], ...] = (
    WaitingForUserError,
    CaptchaDetectedError,
    AuthenticationRequiredError,
)


@dataclass
class TaskContext:
    task: AgentTask
    session: AsyncSession
    container: Container

    @property
    def payload(self) -> dict[str, Any]:
        return self.task.payload

    def uuid(self, key: str) -> uuid.UUID:
        return uuid.UUID(str(self.task.payload[key]))


@dataclass(frozen=True, slots=True)
class ClaimedTask:
    """Immutable snapshot of a claimed task, safe to use across units of work."""

    id: uuid.UUID
    type: TaskType
    user_id: uuid.UUID | None
    attempt_count: int
    max_attempts: int

    @classmethod
    def of(cls, task: AgentTask) -> ClaimedTask:
        return cls(task.id, task.type, task.user_id, task.attempt_count, task.max_attempts)


Handler = Callable[[TaskContext], Awaitable[dict[str, Any] | None]]
_HANDLERS: dict[TaskType, Handler] = {}


def task_handler(task_type: TaskType) -> Callable[[Handler], Handler]:
    def register(fn: Handler) -> Handler:
        if task_type in _HANDLERS and _HANDLERS[task_type] is not fn:
            raise RuntimeError(f"Duplicate handler for {task_type}")
        _HANDLERS[task_type] = fn
        return fn

    return register


def load_handlers() -> None:
    """Import modules that register handlers (kept explicit to avoid import cycles)."""
    import careeros.handlers  # noqa: F401


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, CareerOSError):
        return exc.retryable
    return not isinstance(exc, (ValueError, TypeError, KeyError, AttributeError))


def _message(exc: BaseException) -> str:
    if isinstance(exc, CareerOSError):
        return exc.message[:2000]
    return f"{type(exc).__name__}: {str(exc)[:1800]}"


async def run_task(container: Container, task: ClaimedTask, sessions: SessionFactory) -> TaskStatus:
    """Execute one claimed task. Never raises: outcomes are recorded on the task row."""
    task_id, task_type = task.id, task.type
    attempt_count, max_attempts = task.attempt_count, task.max_attempts
    handler = _HANDLERS.get(task_type)
    with bound_context(task_id=str(task_id), task_type=task_type.value, user_id=str(task.user_id)):
        started = time.perf_counter()
        if handler is None:
            await _finish(sessions, task_id, TaskStatus.FAILED, error=f"No handler for {task_type}")
            return TaskStatus.FAILED
        try:
            async with sessions() as session:
                live = await session.get(AgentTask, task_id, populate_existing=True)
                if live is None:
                    return TaskStatus.CANCELLED
                result = await handler(TaskContext(task=live, session=session, container=container))
                live.status = TaskStatus.COMPLETED
                live.result = result or {}
                live.error = live.error_type = None
                live.completed_at = utcnow()
                live.locked_by = live.locked_until = None
                await session.commit()
        except _WAITING_ERRORS as exc:
            log.info("task_waiting_for_user", reason=exc.code)
            await _finish(
                sessions,
                task_id,
                TaskStatus.WAITING_FOR_USER,
                error=exc.message,
                error_type=exc.code,
            )
            return TaskStatus.WAITING_FOR_USER
        except Exception as exc:
            retry = _is_retryable(exc) and attempt_count < max_attempts
            error_type = exc.code if isinstance(exc, CareerOSError) else type(exc).__name__
            if isinstance(exc, CareerOSError):
                log.warning("task_error", error_type=error_type, error=exc.message, retry=retry)
            else:
                log.error(
                    "task_crashed",
                    error_type=error_type,
                    retry=retry,
                    trace="".join(traceback.format_exception(exc))[-4000:],
                )
            status = TaskStatus.QUEUED if retry else TaskStatus.FAILED
            await _finish(
                sessions,
                task_id,
                status,
                error=_message(exc),
                error_type=error_type,
                run_after=utcnow() + queue.backoff_delay(attempt_count) if retry else None,
            )
            return status
        log.info("task_completed", duration_ms=round((time.perf_counter() - started) * 1000))
        return TaskStatus.COMPLETED


async def _finish(
    sessions: SessionFactory,
    task_id: uuid.UUID,
    status: TaskStatus,
    *,
    error: str | None = None,
    error_type: str | None = None,
    run_after: Any = None,
) -> None:
    async with sessions() as session:
        task = await session.get(AgentTask, task_id, populate_existing=True)
        if task is None:
            return
        task.status = status
        task.error = error
        task.error_type = error_type
        task.locked_by = task.locked_until = None
        if run_after is not None:
            task.run_after = run_after
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = utcnow()
        await session.commit()


class Worker:
    """Polls the queue and runs tasks with bounded concurrency. Also drives the scheduler."""

    SCHEDULER_LOCK_ID = 7_300_001  # pg advisory lock: one scheduler across all workers

    def __init__(
        self,
        container: Container,
        *,
        sessions: SessionFactory | None = None,
        concurrency: int | None = None,
        worker_id: str | None = None,
    ) -> None:
        self.container = container
        self.sessions: SessionFactory = sessions or container.db.session
        self.concurrency = concurrency or container.settings.worker_concurrency
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self._last_maintenance = 0.0

    async def run_once(self, limit: int | None = None) -> int:
        async with self.sessions() as session:
            claimed = [
                ClaimedTask.of(task)
                for task in await queue.claim_batch(
                    session,
                    worker_id=self.worker_id,
                    limit=limit or self.concurrency,
                    lease_seconds=self.container.settings.task_lease_seconds,
                )
            ]
            await session.commit()
        for task in claimed:
            await run_task(self.container, task, self.sessions)
        return len(claimed)

    async def drain(self, max_rounds: int = 100) -> int:
        """Run until the queue has no due tasks (used by tests and one-shot commands)."""
        total = 0
        for _ in range(max_rounds):
            ran = await self.run_once()
            if ran == 0:
                break
            total += ran
        return total

    async def maintenance(self) -> None:
        from careeros.scheduling import tick

        async with self.sessions() as session:
            recovered = await queue.recover_stale(session)
            locked: bool = (
                await session.execute(
                    text("SELECT pg_try_advisory_xact_lock(:id)"), {"id": self.SCHEDULER_LOCK_ID}
                )
            ).scalar_one()
            scheduled: dict[str, int] = {}
            if locked:
                scheduled = await tick(session, self.container)
            await session.commit()
        if recovered or any(scheduled.values()):
            log.info("worker_maintenance", recovered=recovered, **scheduled)

    async def run_forever(self, stop: asyncio.Event) -> None:
        log.info("worker_started", worker_id=self.worker_id, concurrency=self.concurrency)
        semaphore = asyncio.Semaphore(self.concurrency)
        running: set[asyncio.Task[TaskStatus]] = set()
        poll = self.container.settings.worker_poll_interval_seconds
        while not stop.is_set():
            try:
                if time.monotonic() - self._last_maintenance > 60:
                    self._last_maintenance = time.monotonic()
                    await self.maintenance()
                free = self.concurrency - len(running)
                claimed: list[ClaimedTask] = []
                if free > 0:
                    async with self.sessions() as session:
                        claimed = [
                            ClaimedTask.of(task)
                            for task in await queue.claim_batch(
                                session,
                                worker_id=self.worker_id,
                                limit=free,
                                lease_seconds=self.container.settings.task_lease_seconds,
                            )
                        ]
                        await session.commit()
                for task in claimed:
                    running.add(asyncio.create_task(self._guarded(semaphore, task)))
                running = {t for t in running if not t.done()}
            except Exception as exc:  # keep the worker alive through transient DB errors
                log.error("worker_loop_error", error_type=type(exc).__name__, error=str(exc)[:500])
            if not claimed:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), timeout=poll)
        if running:
            await asyncio.gather(*running, return_exceptions=True)
        log.info("worker_stopped", worker_id=self.worker_id)

    async def _guarded(self, semaphore: asyncio.Semaphore, task: ClaimedTask) -> TaskStatus:
        async with semaphore:
            return await run_task(self.container, task, self.sessions)


@asynccontextmanager
async def reuse_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Session factory that hands out one existing session (tests, inline execution).

    Mirrors `Database.session()`: a failure rolls back the work done since the last commit,
    so a crashed handler can never leak partial writes into the task's outcome commit.
    """
    try:
        yield session
    except BaseException:
        await session.rollback()
        raise
