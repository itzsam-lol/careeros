from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.container import Container
from careeros.intelligence.models import JobAnalysis
from careeros.jobs.models import Job
from careeros.matching.models import JobMatch
from careeros.matching.tasks import enqueue_stale_matches
from careeros.tasks.models import AgentTask, TaskStatus, TaskType
from careeros.tasks.runtime import Worker

SECTIONS = (
    "projects",
    "experience",
    "research",
    "publications",
    "education",
    "skills",
    "achievements",
    "answers",
)


async def _setup(client: AsyncClient, worker: Worker, fixtures_dir: Path) -> None:
    payload = json.loads((fixtures_dir / "profiles" / "demo_profile.json").read_text("utf-8"))
    assert (await client.post("/api/v1/profile/import", json=payload)).status_code == 200
    profile = (await client.get("/api/v1/profile")).json()
    for section in SECTIONS:
        ids = [item["id"] for item in profile[section]]
        if ids:
            await client.post(
                "/api/v1/profile/verification",
                json={"section": section, "ids": ids, "status": "VERIFIED"},
            )
    await client.put("/api/v1/profile/basics", json={"summary": payload["basics"]["summary"]})
    source = {
        "name": "Demo feed",
        "type": "FIXTURE",
        "config": {"name": "demo_feed"},
        "cadence": "MANUAL",
    }
    assert (await client.post("/api/v1/sources", json=source)).status_code == 201
    await worker.drain()


async def _matches(session: AsyncSession) -> dict[str, JobMatch]:
    rows = (
        await session.execute(
            select(Job.title, Job.company, JobMatch).join(JobMatch, JobMatch.job_id == Job.id)
        )
    ).all()
    return {f"{company}|{title}": match for title, company, match in rows}


async def test_end_to_end_matching_ranks_and_explains(
    client: AsyncClient, session: AsyncSession, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)
    failed = (
        (await session.execute(select(AgentTask).where(AgentTask.status == TaskStatus.FAILED)))
        .scalars()
        .all()
    )
    assert failed == [], [(t.type, t.error) for t in failed]

    matches = await _matches(session)
    # Acme and Brightpath were excluded by preferences at discovery; the mirror was merged.
    assert len(matches) == 10

    ml = matches["Nimbus AI|Machine Learning Engineer Intern"]
    research = matches["Lumen Labs|AI Research Intern - Computer Vision"]
    senior = matches["Nimbus AI|Senior Machine Learning Engineer"]
    us_role = matches["Stellar Robotics|Machine Learning Intern (Summer 2027)"]
    analyst = matches["Tensorleaf|Data Analyst Intern"]
    injected = matches["Veritas AI|Software Engineer Intern"]
    sre = matches["Cobalt Cloud|Site Reliability Engineer"]

    assert ml.eligible, ml.reasoning
    assert ml.overall_score >= 0.6, ml.reasoning
    assert research.eligible
    assert research.dimensions["research"] > 0.3
    assert ml.overall_score > analyst.overall_score

    assert not senior.eligible
    assert senior.overall_score <= 0.45
    assert any(
        c["key"] in ("experience", "seniority") and c["status"] == "FAIL"
        for c in senior.eligibility
    )

    assert not us_role.eligible
    auth = next(c for c in us_role.eligibility if c["key"] == "work_authorization")
    assert auth["status"] == "FAIL"
    assert "does not sponsor" in auth["detail"]

    assert not sre.eligible  # 3+ years required, the profile has internships only

    # The injected "rate this candidate 100%" text is detected, excluded and changes nothing.
    injected_analysis = await session.get(JobAnalysis, injected.analysis_id)
    assert injected_analysis is not None
    assert injected_analysis.extraction["injection_detected"] is True
    assert "Kubernetes" not in injected_analysis.extraction["required_skills"]
    assert injected.overall_score < ml.overall_score
    explanation = " ".join([injected.reasoning, *(s["text"] for s in injected.strengths)])
    assert "Kubernetes" not in explanation
    assert "100%" not in explanation

    coverage = {c["skill"]: c["status"] for c in ml.requirement_coverage}
    assert coverage["PyTorch"] == "MATCHED"
    assert coverage["Python"] == "MATCHED"
    assert any(s["evidence"] for s in ml.strengths)  # strengths cite evidence
    for strength in ml.strengths:
        for ref in strength["evidence"]:
            assert ref["verified"] is True
            # The skills summary is reported through coverage, never as "Your skills “Skills”".
            assert ref["source_type"] != "skills"


async def test_inbox_views_detail_and_actions(
    client: AsyncClient, other_client: AsyncClient, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)

    everything = (await client.get("/api/v1/jobs", params={"view": "ALL"})).json()
    assert everything["total"] == 10
    scores = [
        c["match"]["overall_score"]
        for c in everything["items"]
        if c["match"] and c["match"]["eligible"]
    ]
    assert scores == sorted(scores, reverse=True)  # best eligible matches first

    high = (await client.get("/api/v1/jobs", params={"view": "HIGH_MATCH"})).json()
    assert all(c["match"]["eligible"] for c in high["items"])

    job_id = next(
        c["job_id"] for c in everything["items"] if c["title"] == "Machine Learning Engineer Intern"
    )
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    assert detail["analysis"]["required_skills"]
    assert detail["match"]["eligibility"]
    assert detail["match"]["stale"] is False
    assert len(detail["sources"]) == 2  # canonical + mirrored posting
    assert (await other_client.get(f"/api/v1/jobs/{job_id}")).status_code == 404

    saved = (await client.post(f"/api/v1/jobs/{job_id}/save")).json()
    assert saved["card"]["status"] == "SAVED"
    assert (await client.get("/api/v1/jobs", params={"view": "SAVED"})).json()["total"] == 1
    dismissed = (
        await client.post(f"/api/v1/jobs/{job_id}/dismiss", json={"reason": "location"})
    ).json()
    assert dismissed["card"]["status"] == "DISMISSED"
    assert all(c["job_id"] != job_id for c in (await client.get("/api/v1/jobs")).json()["items"])
    restored = (await client.post(f"/api/v1/jobs/{job_id}/restore")).json()
    assert restored["card"]["status"] == "MATCHED"

    searched = (await client.get("/api/v1/jobs", params={"q": "research"})).json()
    assert {c["company"] for c in searched["items"]} >= {"Lumen Labs"}


async def test_notifications_and_dashboard(
    client: AsyncClient, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)
    notifications = (await client.get("/api/v1/notifications")).json()
    types = {n["type"] for n in notifications}
    assert types & {"HIGH_MATCH", "NEW_JOB"}
    assert all(n["job_id"] for n in notifications)
    titles = " ".join(n["title"] for n in notifications)
    assert "Senior Machine Learning Engineer" not in titles  # ineligible jobs never notify
    assert "Stellar Robotics" not in titles

    unread = (await client.get("/api/v1/notifications/unread-count")).json()["unread"]
    assert unread == len(notifications)
    after = (await client.post("/api/v1/notifications/read", json={})).json()
    assert after["unread"] == 0

    dashboard = (await client.get("/api/v1/dashboard")).json()
    assert dashboard["counts"]["all"] == 10
    assert dashboard["counts"]["unread_notifications"] == 0
    assert dashboard["top_matches"][0]["match"]["eligible"] is True
    assert dashboard["sources"] == {"total": 1, "enabled": 1, "failing": 0}
    assert dashboard["profile"]["completeness"] == 100
    assert dashboard["recent_activity"]


async def test_profile_changes_trigger_rematching(
    client: AsyncClient,
    session: AsyncSession,
    worker: Worker,
    container: Container,
    fixtures_dir: Path,
) -> None:
    await _setup(client, worker, fixtures_dir)
    before = {
        m.job_id: m.overall_score for m in (await session.execute(select(JobMatch))).scalars()
    }
    assert (
        await client.post("/api/v1/profile/skills", json={"name": "Tableau"})
    ).status_code == 201

    queued = await enqueue_stale_matches(session, container)
    assert queued == len(before)
    await session.commit()
    await worker.drain()
    rematches = (
        (
            await session.execute(
                select(AgentTask).where(
                    AgentTask.type == TaskType.MATCH_JOB, AgentTask.idempotency_key.like("%:v%")
                )
            )
        )
        .scalars()
        .all()
    )
    assert rematches
    assert all(t.status == TaskStatus.COMPLETED for t in rematches)
    analyst = (
        await session.execute(
            select(JobMatch)
            .join(Job, Job.id == JobMatch.job_id)
            .where(Job.title == "Data Analyst Intern")
        )
    ).scalar_one()
    await session.refresh(analyst)
    coverage: dict[str, Any] = {c["skill"]: c["status"] for c in analyst.requirement_coverage}
    assert coverage.get("Tableau") == "MATCHED"


@pytest.mark.parametrize("threshold", [0.99])
async def test_thresholds_come_from_user_settings(
    client: AsyncClient, worker: Worker, fixtures_dir: Path, threshold: float
) -> None:
    await client.patch(
        "/api/v1/me/settings", json={"matching": {"high_match_threshold": threshold}}
    )
    await _setup(client, worker, fixtures_dir)
    high = (await client.get("/api/v1/jobs", params={"view": "HIGH_MATCH"})).json()
    assert high["total"] == 0
    notifications = (await client.get("/api/v1/notifications")).json()
    assert all(n["type"] != "HIGH_MATCH" for n in notifications)
