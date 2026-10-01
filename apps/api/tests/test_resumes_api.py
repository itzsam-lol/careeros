from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.container import Container
from careeros.core.clock import utcnow
from careeros.jobs.models import Job, UserJob
from careeros.matching.service import AUTO_DISMISS_NO_SPONSORSHIP
from careeros.matching.tasks import create_follow_up_reminders
from careeros.resumes.latex import find_engine
from careeros.tasks.runtime import Worker
from tests.test_matching import _setup

needs_latex = pytest.mark.skipif(find_engine() is None, reason="no LaTeX engine installed")


async def _job_id(session: AsyncSession, title: str) -> str:
    job = (await session.execute(select(Job).where(Job.title == title))).scalars().first()
    assert job is not None
    return str(job.id)


async def test_master_upload_validation(client: AsyncClient, fixtures_dir: Path) -> None:
    assert (await client.get("/api/v1/resumes/master")).json() is None
    bad = await client.put("/api/v1/resumes/master", json={"tex": "no document here " * 5})
    assert bad.status_code == 422
    tex = (fixtures_dir / "resumes" / "sample_resume.tex").read_text("utf-8")
    ok = await client.put("/api/v1/resumes/master", json={"tex": tex, "filename": "alex.tex"})
    assert ok.status_code == 200
    body = ok.json()
    assert body["revision"] == 1
    assert body["filename"] == "alex.tex"
    assert [s["role"] for s in body["sections"]] == [
        "summary",
        "education",
        "experience",
        "projects",
        "leadership",
        "skills",
    ]
    again = await client.put("/api/v1/resumes/master", json={"tex": tex})
    assert again.json()["revision"] == 2


async def test_resume_needs_a_master(client: AsyncClient) -> None:
    response = await client.post("/api/v1/resumes", json={"kind": "RESUME"})
    assert response.status_code == 422


@needs_latex
@pytest.mark.latex
async def test_tailored_resume_and_cover_letter_end_to_end(
    client: AsyncClient,
    other_client: AsyncClient,
    session: AsyncSession,
    worker: Worker,
    fixtures_dir: Path,
) -> None:
    await _setup(client, worker, fixtures_dir)
    tex = (fixtures_dir / "resumes" / "sample_resume.tex").read_text("utf-8")
    await client.put("/api/v1/resumes/master", json={"tex": tex})
    await worker.drain()
    master = (await client.get("/api/v1/resumes/master")).json()
    assert master["has_pdf"]
    assert master["pages"] == 1
    assert master["compile_error"] is None

    job_id = await _job_id(session, "Backend Engineer Intern")
    created = await client.post("/api/v1/resumes", json={"job_id": job_id, "kind": "RESUME"})
    assert created.status_code == 202
    assert created.json()["status"] == "PENDING"
    letter = await client.post(
        "/api/v1/resumes",
        json={"job_id": job_id, "kind": "COVER_LETTER", "options": {"tone": "concise"}},
    )
    assert letter.status_code == 202
    await worker.drain()

    resume = (await client.get(f"/api/v1/resumes/{created.json()['id']}")).json()
    assert resume["status"] == "READY", resume["error"]
    assert resume["pages"] == 1
    assert resume["coverage_after"] >= resume["coverage_before"]
    assert resume["changes"]
    pdf = await client.get(f"/api/v1/resumes/{resume['id']}/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    cover = (await client.get(f"/api/v1/resumes/{letter.json()['id']}")).json()
    assert cover["status"] == "READY"
    assert "Quasar Health" in cover["body"]
    assert "used each of these" not in cover["body"]  # never over-claims experience
    assert "Backend Engineer Intern" in cover["body"]

    # A ready notification links to the document.
    notifications = (await client.get("/api/v1/notifications")).json()
    assert any(n["type"] == "RESUME_READY" for n in notifications)

    # Signed links work without auth and expire; other users cannot see the document.
    link = (await client.post(f"/api/v1/resumes/{resume['id']}/link")).json()
    path = link["url"].split("://", 1)[1].split("/", 1)[1]
    anonymous = await other_client.get("/" + path, headers={"Authorization": ""})
    assert anonymous.status_code == 200
    assert anonymous.content.startswith(b"%PDF")
    tampered = await other_client.get(f"/api/v1/resumes/{resume['id']}/download?token=1.abcdef")
    assert tampered.status_code == 401
    assert (await other_client.get(f"/api/v1/resumes/{resume['id']}")).status_code == 404

    listing = (await client.get("/api/v1/resumes", params={"job_id": job_id})).json()
    assert {d["kind"] for d in listing} == {"RESUME", "COVER_LETTER"}
    assert (await client.patch(f"/api/v1/resumes/{resume['id']}", json={"starred": True})).json()[
        "starred"
    ] is True
    assert (await client.delete(f"/api/v1/resumes/{letter.json()['id']}")).status_code == 204


async def test_prep_and_outreach_are_grounded(
    client: AsyncClient, session: AsyncSession, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(session, "Machine Learning Engineer Intern")
    prep = (await client.get(f"/api/v1/jobs/{job_id}/prep")).json()
    statuses = {p["topic"]: p["status"] for p in prep["talking_points"]}
    assert statuses.get("PyTorch") == "STRONG"
    # Quoted achievements name the skill, or the item is cited as "built with <skill>".
    for point in prep["talking_points"]:
        for line in point["evidence"]:
            story = line.split(": ", 1)[1]
            assert point["topic"].lower() in story.lower(), line
    assert prep["behavioural"]
    assert prep["questions_to_ask"]
    drafts = (await client.get(f"/api/v1/jobs/{job_id}/outreach")).json()
    assert {d["kind"] for d in drafts} == {
        "connection_note",
        "referral_request",
        "follow_up",
        "thank_you",
    }
    note = next(d for d in drafts if d["kind"] == "connection_note")
    assert len(note["body"]) <= 300
    assert "Nimbus AI" in note["body"]


async def test_application_tracking(
    client: AsyncClient, session: AsyncSession, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(session, "Data Analyst Intern")
    applied = await client.patch(
        f"/api/v1/jobs/{job_id}/application",
        json={"stage": "APPLIED", "note": "Applied via portal"},
    )
    body = applied.json()
    assert body["stage"] == "APPLIED"
    assert body["applied_at"]
    assert body["follow_up_at"]
    assert body["note"] == "Applied via portal"
    interview = (
        await client.patch(f"/api/v1/jobs/{job_id}/application", json={"stage": "INTERVIEW"})
    ).json()
    assert [h["stage"] for h in interview["history"]] == ["APPLIED", "INTERVIEW"]
    tracker = (await client.get("/api/v1/jobs", params={"view": "APPLIED"})).json()
    assert [c["application_stage"] for c in tracker["items"]] == ["INTERVIEW"]
    rejected = (
        await client.patch(f"/api/v1/jobs/{job_id}/application", json={"stage": "REJECTED"})
    ).json()
    assert rejected["follow_up_at"] is None
    counts = (await client.get("/api/v1/dashboard")).json()["counts"]
    assert counts["applied"] == 1


async def test_sponsorship_only_countries_hide_roles(
    client: AsyncClient, session: AsyncSession, worker: Worker, fixtures_dir: Path
) -> None:
    await client.put(
        "/api/v1/profile/preferences", json={"sponsorship_required_countries": ["United States"]}
    )
    await _setup(client, worker, fixtures_dir)
    # _setup's import replaces preferences; apply the rule again and re-match.
    await client.put(
        "/api/v1/profile/preferences",
        json={
            "sponsorship_required_countries": ["United States"],
            "target_countries": ["India", "United States"],
        },
    )
    job_id = await _job_id(session, "Machine Learning Intern (Summer 2027)")
    await client.post(f"/api/v1/jobs/{job_id}/rematch")
    await worker.drain()
    user_job = (
        (await session.execute(select(UserJob).where(UserJob.job_id == job_id))).scalars().first()
    )
    assert user_job is not None
    await session.refresh(user_job)
    assert user_job.status.value == "DISMISSED"
    assert user_job.dismiss_reason == AUTO_DISMISS_NO_SPONSORSHIP
    detail = (await client.get(f"/api/v1/jobs/{job_id}")).json()
    auth = next(c for c in detail["match"]["eligibility"] if c["key"] == "work_authorization")
    assert auth["status"] == "FAIL"
    assert "visa sponsorship" in auth["detail"]


async def test_follow_up_reminders_fire_once_when_due(
    client: AsyncClient,
    session: AsyncSession,
    worker: Worker,
    container: Container,
    fixtures_dir: Path,
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(session, "Machine Learning Engineer Intern")
    yesterday = (utcnow() - timedelta(days=1)).isoformat()
    response = await client.patch(
        f"/api/v1/jobs/{job_id}/application", json={"stage": "APPLIED", "follow_up_at": yesterday}
    )
    assert response.status_code == 200

    assert await create_follow_up_reminders(session, container) == 1
    assert await create_follow_up_reminders(session, container) == 0  # once per follow-up date
    reminders = [
        n
        for n in (await client.get("/api/v1/notifications")).json()
        if n["type"] == "FOLLOW_UP_DUE"
    ]
    assert len(reminders) == 1
    assert reminders[0]["job_id"] == job_id


async def test_apply_kit_collects_answers_from_the_verified_profile(
    client: AsyncClient, session: AsyncSession, worker: Worker, fixtures_dir: Path
) -> None:
    await _setup(client, worker, fixtures_dir)
    job_id = await _job_id(session, "Machine Learning Engineer Intern")
    kit = (await client.get(f"/api/v1/jobs/{job_id}/apply-kit")).json()
    fields = {f["label"]: f["value"] for f in kit["fields"]}
    assert fields["Full name"]
    assert "University" in fields
    assert fields["Work authorisation"].startswith("Yes, I am authorised to work in India")
    assert "Machine Learning Engineer Intern" in kit["why_company"]
    assert "Nimbus AI" in kit["why_company"]
    assert kit["apply_url"]
    assert kit["documents"] == []
