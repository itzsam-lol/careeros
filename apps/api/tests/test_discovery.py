from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.container import Container
from careeros.core.clock import utcnow
from careeros.discovery.adapters.fixture import FixtureAdapter
from careeros.discovery.models import JobSource
from careeros.discovery.raw import RawJob
from careeros.events.models import DomainEvent, EventType
from careeros.jobs.models import Job, JobLifecycle, JobSourceLink, UserJob
from careeros.scheduling import schedule_due_sources
from careeros.tasks.models import AgentTask, TaskStatus, TaskType
from careeros.tasks.runtime import Worker

FIXTURE_SOURCE = {
    "name": "Demo feed",
    "type": "FIXTURE",
    "config": {"name": "demo_feed"},
    "cadence": "MANUAL",
}


async def _exclude_demo_noise(client: AsyncClient) -> None:
    response = await client.put(
        "/api/v1/profile/preferences",
        json={"excluded_companies": ["Acme Gambling Co"], "excluded_keywords": ["sales engineer"]},
    )
    assert response.status_code == 200


async def _count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(
        (await session.execute(select(func.count()).select_from(model).where(*where))).scalar_one()
    )


async def test_fixture_source_discovers_deduplicates_and_filters(
    client: AsyncClient, session: AsyncSession, worker: Worker
) -> None:
    await _exclude_demo_noise(client)
    created = await client.post("/api/v1/sources", json=FIXTURE_SOURCE)
    assert created.status_code == 201, created.text
    source = created.json()
    assert source["health"] == "never_run"

    await worker.drain()

    jobs = list((await session.execute(select(Job))).scalars())
    titles = {job.title for job in jobs}
    assert len(jobs) == 10  # 13 postings - 2 excluded - 1 mirrored duplicate
    assert "Sales Engineer" not in titles
    assert not any(job.company == "Acme Gambling Co" for job in jobs)

    nimbus = next(j for j in jobs if j.title == "Machine Learning Engineer Intern")
    links = await _count(session, JobSourceLink, JobSourceLink.job_id == nimbus.id)
    assert links == 2  # the mirror posting was merged into the canonical job
    assert nimbus.countries == ["India"]
    assert nimbus.deadline is not None

    assert await _count(session, UserJob) == 10
    completed = (
        await session.execute(
            select(DomainEvent).where(DomainEvent.type == EventType.DISCOVERY_COMPLETED)
        )
    ).scalar_one()
    assert completed.payload["found"] == 13
    assert completed.payload["filtered"] == 2
    assert completed.payload["duplicates"] == 1
    assert completed.payload["new_for_user"] == 10

    analyze = await _count(session, AgentTask, AgentTask.type == TaskType.ANALYZE_JOB)
    assert analyze == 10  # every new job is queued for JD analysis exactly once

    health = (await client.get("/api/v1/sources")).json()[0]
    assert health["health"] == "healthy"
    assert health["last_jobs_found"] == 13


async def test_rerun_is_idempotent_and_closes_vanished_postings(
    client: AsyncClient, session: AsyncSession, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = (await client.post("/api/v1/sources", json=FIXTURE_SOURCE)).json()
    await worker.drain()
    before = await _count(session, UserJob)

    original = FixtureAdapter.discover_jobs

    async def without_cobalt(self: FixtureAdapter) -> list[RawJob]:
        return [job for job in await original(self) if job.company != "Cobalt Cloud"]

    monkeypatch.setattr(FixtureAdapter, "discover_jobs", without_cobalt)
    assert (await client.post(f"/api/v1/sources/{source['id']}/run")).status_code == 202
    await worker.drain()

    assert await _count(session, UserJob) == before  # nothing duplicated
    cobalt = (await session.execute(select(Job).where(Job.company == "Cobalt Cloud"))).scalar_one()
    assert cobalt.is_active is False
    status = (
        await session.execute(select(UserJob.status).where(UserJob.job_id == cobalt.id))
    ).scalar_one()
    assert status == JobLifecycle.CLOSED


async def test_failing_source_records_health_without_crashing(
    client: AsyncClient, session: AsyncSession, worker: Worker
) -> None:
    broken = {**FIXTURE_SOURCE, "name": "Broken", "config": {"name": "does-not-exist"}}
    source = (await client.post("/api/v1/sources", json=broken)).json()
    await worker.drain()
    refreshed = (await client.get("/api/v1/sources")).json()[0]
    assert refreshed["id"] == source["id"]
    assert refreshed["consecutive_failures"] == 1
    assert "Unknown fixture feed" in refreshed["last_error"]
    assert refreshed["health"] == "degraded"
    failed = await _count(session, DomainEvent, DomainEvent.type == EventType.DISCOVERY_FAILED)
    assert failed == 1


async def test_source_api_validation_and_isolation(
    client: AsyncClient, other_client: AsyncClient
) -> None:
    bad = await client.post(
        "/api/v1/sources",
        json={"name": "x", "type": "GREENHOUSE", "config": {"board_token": "../x"}},
    )
    assert bad.status_code == 422
    unknown_field = await client.post(
        "/api/v1/sources",
        json={"name": "x", "type": "LEVER", "config": {"company": "acme", "evil": 1}},
    )
    assert unknown_field.status_code == 422

    source = (await client.post("/api/v1/sources", json=FIXTURE_SOURCE)).json()
    duplicate = await client.post("/api/v1/sources", json=FIXTURE_SOURCE)
    assert duplicate.status_code == 409

    url = f"/api/v1/sources/{source['id']}"
    assert (await other_client.patch(url, json={"enabled": False})).status_code == 404
    assert (await other_client.delete(url)).status_code == 404
    assert (await other_client.post(f"{url}/run")).status_code == 404
    assert (await other_client.get("/api/v1/sources")).json() == []

    hourly = await client.patch(url, json={"cadence": "HOURLY"})
    assert hourly.json()["next_run_at"] is not None
    assert (await client.delete(url)).status_code == 204


async def test_scheduler_enqueues_due_sources_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    source = (
        await client.post("/api/v1/sources", json={**FIXTURE_SOURCE, "cadence": "HOURLY"})
    ).json()
    row = await session.get(JobSource, source["id"])
    assert row is not None
    row.next_run_at = utcnow() - timedelta(minutes=1)
    await session.flush()

    assert await schedule_due_sources(session) == 1
    assert await schedule_due_sources(session) == 0  # not due again for an hour
    row.next_run_at = utcnow() - timedelta(minutes=1)  # a duplicate tick in the same slot
    await session.flush()
    await schedule_due_sources(session)
    scheduled = await _count(
        session,
        AgentTask,
        AgentTask.type == TaskType.RUN_DISCOVERY,
        AgentTask.idempotency_key.like(f"discovery:{source['id']}:%"),
        AgentTask.idempotency_key.not_like("%:initial"),
    )
    assert scheduled == 1


async def test_activity_feed_and_tasks_endpoints(client: AsyncClient, worker: Worker) -> None:
    await client.post("/api/v1/sources", json=FIXTURE_SOURCE)
    await worker.drain()
    activity = (await client.get("/api/v1/activity")).json()
    assert any(event["type"] == "DISCOVERY_COMPLETED" for event in activity)
    assert any(event["type"] == "JOB_DISCOVERED" for event in activity)
    tasks = (await client.get("/api/v1/tasks", params={"limit": 200})).json()
    discovery = [t for t in tasks if t["type"] == "RUN_DISCOVERY"]
    assert discovery[0]["status"] == "COMPLETED"
    assert discovery[0]["result"]["stats"]["found"] == 13


async def test_global_jobs_are_shared_but_inboxes_are_private(
    client: AsyncClient, other_client: AsyncClient, session: AsyncSession, worker: Worker
) -> None:
    await client.post("/api/v1/sources", json=FIXTURE_SOURCE)
    await other_client.post("/api/v1/sources", json=FIXTURE_SOURCE)
    await worker.drain()
    assert await _count(session, Job) == 12  # no preferences: 13 postings - 1 mirror
    assert await _count(session, UserJob) == 24  # each user gets their own inbox entries
    analyze = await _count(session, AgentTask, AgentTask.type == TaskType.ANALYZE_JOB)
    assert analyze == 12  # analysis is shared per job, not per user


async def test_task_policy_retry_fail_wait_and_recover(
    container: Container, session: AsyncSession, worker: Worker, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careeros.core.errors import CaptchaDetectedError, SourceFetchError
    from careeros.tasks import queue, runtime

    outcomes: list[Exception | None] = [
        SourceFetchError("temporary", retryable=True),
        SourceFetchError("permanent", retryable=False),
        CaptchaDetectedError("captcha on the portal"),
        None,
    ]

    async def flaky(ctx: runtime.TaskContext) -> dict[str, Any]:
        outcome = outcomes.pop(0)
        if outcome is not None:
            raise outcome
        return {"ok": True}

    monkeypatch.setitem(runtime._HANDLERS, TaskType.CHECK_DEADLINES, flaky)
    ids = [
        await queue.enqueue(session, TaskType.CHECK_DEADLINES, {"n": n}, max_attempts=3)
        for n in range(4)
    ]
    await session.commit()
    await worker.run_once(limit=4)

    tasks = {
        t.id: t
        for t in (await session.execute(select(AgentTask).where(AgentTask.id.in_(ids)))).scalars()
    }
    for task in tasks.values():
        await session.refresh(task)
    states = [tasks[i].status for i in ids]
    assert states == [
        TaskStatus.QUEUED,  # retryable: back in the queue with backoff
        TaskStatus.FAILED,
        TaskStatus.WAITING_FOR_USER,
        TaskStatus.COMPLETED,
    ]
    assert tasks[ids[0]].run_after > utcnow()
    assert tasks[ids[0]].attempt_count == 1
    assert tasks[ids[3]].result == {"ok": True}

    # A crashed worker leaves a RUNNING task with an expired lease; it is recovered.
    stale = tasks[ids[3]]
    stale.status = TaskStatus.RUNNING
    stale.locked_until = utcnow() - timedelta(seconds=1)
    await session.commit()
    assert await queue.recover_stale(session) == 1
