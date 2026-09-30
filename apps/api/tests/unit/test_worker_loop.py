"""The worker loop keeps its slots busy instead of idling a poll interval between tasks."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from careeros.tasks import runtime
from careeros.tasks.models import TaskStatus, TaskType


class _Session:
    async def commit(self) -> None:
        return None


@asynccontextmanager
async def _sessions() -> AsyncIterator[Any]:
    yield _Session()


async def test_worker_claims_more_as_soon_as_a_slot_frees(monkeypatch: pytest.MonkeyPatch) -> None:
    total = 12
    pending = [
        SimpleNamespace(
            id=uuid.uuid4(), type=TaskType.MATCH_JOB, user_id=None, attempt_count=0, max_attempts=5
        )
        for _ in range(total)
    ]
    done: list[uuid.UUID] = []
    stop = asyncio.Event()

    async def claim_batch(
        session: Any, *, worker_id: str, limit: int, lease_seconds: int
    ) -> list[Any]:
        batch = pending[:limit]
        del pending[:limit]
        return batch

    async def run_task(container: Any, task: runtime.ClaimedTask, sessions: Any) -> TaskStatus:
        await asyncio.sleep(0.02)
        done.append(task.id)
        if len(done) == total:
            stop.set()
        return TaskStatus.COMPLETED

    monkeypatch.setattr(runtime.queue, "claim_batch", claim_batch)
    monkeypatch.setattr(runtime, "run_task", run_task)
    settings = SimpleNamespace(
        worker_concurrency=3, worker_poll_interval_seconds=5.0, task_lease_seconds=60
    )
    worker = runtime.Worker(
        SimpleNamespace(settings=settings),  # type: ignore[arg-type]
        sessions=_sessions,
        worker_id="test",
    )
    worker._last_maintenance = time.monotonic()  # skip the scheduler pass

    started = time.monotonic()
    await asyncio.wait_for(worker.run_forever(stop), timeout=10)

    assert len(done) == total
    # 12 tasks of 20 ms over 3 slots. Waiting out the 5 s poll whenever every slot was busy
    # would take well over 10 s.
    assert time.monotonic() - started < 2
