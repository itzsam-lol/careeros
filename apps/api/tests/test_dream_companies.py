from __future__ import annotations

from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.container import Container
from careeros.core.enums import SeniorityLevel
from careeros.jobs.models import Job, UserJob
from careeros.matching.dream import is_dream_company
from careeros.resumes.models import DocumentKind, ResumeDocument
from careeros.resumes.prepare import announce_ready_kits, enqueue_kit_preparation
from careeros.tasks.runtime import Worker
from tests.test_matching import _setup


@pytest.mark.parametrize(
    ("company", "dream", "expected"),
    [
        ("Amazon", ["Amazon"], True),
        ("Amazon Web Services", ["amazon"], True),
        ("NatWest Group", ["NatWest"], True),
        ("NatWest Group", ["NatWest Group"], True),
        ("Nimbus AI Pvt. Ltd.", ["Nimbus AI"], True),
        ("Metadata Inc", ["Meta"], False),
        ("Amazing Labs", ["Amazon"], False),
        ("Amazon", [], False),
    ],
)
def test_dream_companies_match_on_leading_words(
    company: str, dream: list[str], expected: bool
) -> None:
    assert is_dream_company(company, dream) is expected


async def _prepare_and_announce(
    session: AsyncSession, container: Container, worker: Worker
) -> None:
    await enqueue_kit_preparation(session, container)
    await worker.drain()
    await announce_ready_kits(session, container)


async def _notifications(client: AsyncClient) -> list[dict[str, object]]:
    return (await client.get("/api/v1/notifications", params={"limit": 100})).json()


async def test_fresher_roles_at_dream_companies_get_a_kit_and_one_alert(
    client: AsyncClient,
    session: AsyncSession,
    container: Container,
    worker: Worker,
    fixtures_dir: Path,
) -> None:
    await _setup(client, worker, fixtures_dir, preferences={"target_companies": ["Nimbus AI"]})
    intern = (
        await session.execute(
            select(Job).where(
                Job.company.like("Nimbus%"), Job.title == "Machine Learning Engineer Intern"
            )
        )
    ).scalar_one()
    senior = (
        await session.execute(select(Job).where(Job.title == "Senior Machine Learning Engineer"))
    ).scalar_one()
    assert intern.seniority == SeniorityLevel.INTERN
    # The usual match alert waits for the kit, so the role is announced once, when it is ready.
    assert not [n for n in await _notifications(client) if n["job_id"] == str(intern.id)]

    await _prepare_and_announce(session, container, worker)

    user_jobs = {uj.job_id: uj for uj in (await session.execute(select(UserJob))).scalars()}
    assert user_jobs[intern.id].prepared_at is not None
    assert user_jobs[senior.id].prepared_at is None  # ineligible: no kit, no alert
    kinds = {
        d.kind
        for d in (
            await session.execute(select(ResumeDocument).where(ResumeDocument.job_id == intern.id))
        ).scalars()
    }
    assert DocumentKind.COVER_LETTER in kinds  # the résumé needs a master; the letter does not

    ready = [n for n in await _notifications(client) if n["type"] == "APPLICATION_READY"]
    assert len(ready) == 1
    assert ready[0]["title"] == "Ready to apply: Machine Learning Engineer Intern at Nimbus AI"
    assert ready[0]["job_id"] == str(intern.id)
    assert ready[0]["data"]["apply_kit"] is True
    assert ready[0]["priority"] == "HIGH"
    assert not any(n["job_id"] == str(senior.id) for n in await _notifications(client))

    listed = (await client.get("/api/v1/jobs", params={"view": "READY"})).json()["items"]
    assert [item["job_id"] for item in listed] == [str(intern.id)]
    counts = (await client.get("/api/v1/dashboard")).json()["counts"]
    assert counts["ready"] == 1

    # Nothing is announced or prepared twice.
    await _prepare_and_announce(session, container, worker)
    assert len([n for n in await _notifications(client) if n["type"] == "APPLICATION_READY"]) == 1

    # Marking it applied takes it off the ready list; the stage stays the user's to set.
    await client.patch(f"/api/v1/jobs/{intern.id}/application", json={"stage": "APPLIED"})
    assert (await client.get("/api/v1/jobs", params={"view": "READY"})).json()["items"] == []


async def test_many_ready_roles_get_a_single_summary_alert(
    client: AsyncClient,
    session: AsyncSession,
    container: Container,
    worker: Worker,
    fixtures_dir: Path,
) -> None:
    dream = ["Nimbus AI", "Lumen Labs", "Quasar Health", "Tensorleaf", "Veritas AI"]
    await _setup(client, worker, fixtures_dir, preferences={"target_companies": dream})
    await _prepare_and_announce(session, container, worker)

    ready = [n for n in await _notifications(client) if n["type"] == "APPLICATION_READY"]
    prepared = [uj for uj in (await session.execute(select(UserJob))).scalars() if uj.prepared_at]
    assert len(prepared) > 3
    assert len(ready) == 1
    assert ready[0]["job_id"] is None
    assert ready[0]["data"] == {"view": "READY", "count": len(prepared)}
    assert str(ready[0]["title"]).startswith(f"{len(prepared)} fresher roles ready to apply at ")
    # The roles' own match alerts were held back for the kit, so nothing arrives twice; roles
    # elsewhere alert as usual.
    prepared_ids = {str(uj.job_id) for uj in prepared}
    usual = [n for n in await _notifications(client) if n["type"] in ("NEW_JOB", "HIGH_MATCH")]
    assert usual
    assert not [n for n in usual if n["job_id"] in prepared_ids]
