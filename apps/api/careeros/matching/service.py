"""Matching orchestration: eligibility -> coverage -> retrieval -> scores -> explanation -> notify."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.config import LLMTask
from careeros.core.clock import utcnow
from careeros.core.errors import NotFoundError
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.evidence.service import ensure_indexed, search_evidence
from careeros.intelligence.extraction import JobExtraction
from careeros.intelligence.service import job_embedding_text, latest_analysis
from careeros.jobs.models import Job, JobLifecycle, UserJob
from careeros.matching.coverage import requirement_coverage
from careeros.matching.eligibility import evaluate_eligibility, is_eligible
from careeros.matching.explain import explain, label_for
from careeros.matching.models import JobMatch
from careeros.matching.profile_view import build_match_profile
from careeros.matching.scoring import SCORER_VERSION, compute_scores
from careeros.notifications.models import NotificationPriority, NotificationType
from careeros.notifications.service import notify
from careeros.profile.enums import VerificationStatus
from careeros.profile.service import get_profile, load_snapshot
from careeros.users.models import User
from careeros.users.service import read_settings

if TYPE_CHECKING:
    from careeros.container import Container


async def match_job(
    session: AsyncSession, *, user_id: uuid.UUID, job_id: uuid.UUID, container: Container
) -> JobMatch | None:
    user = await session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    profile = await get_profile(session, user)
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    analysis = await latest_analysis(session, job.id)
    if profile is None or analysis is None:
        return None  # matched later: profile creation / analysis completion re-triggers this

    router = container.llm
    embedder = router.embedder
    settings = read_settings(user)
    extraction = JobExtraction.model_validate(analysis.extraction)
    await ensure_indexed(session, profile, embedder)
    snapshot = await load_snapshot(session, profile)
    now = utcnow()
    mp = build_match_profile(snapshot, today=now.date())

    checks = evaluate_eligibility(job, extraction, mp, now=now)
    eligible = is_eligible(checks)
    coverage = requirement_coverage(extraction, mp)
    if job.embedding is None or job.embedding_model != embedder.model:
        job.embedding = await embedder.embed_query(job_embedding_text(job, extraction))
        job.embedding_model = embedder.model
    hits = await search_evidence(
        session,
        profile.id,
        job.embedding,
        embedder,
        limit=12,
        statuses=(VerificationStatus.VERIFIED, VerificationStatus.UNVERIFIED),
    )
    scores = compute_scores(
        job=job,
        extraction=extraction,
        mp=mp,
        coverage=coverage,
        hits=hits,
        checks=checks,
        eligible=eligible,
    )
    # Expensive reasoning only where it matters (spec §53): eligible, promising matches.
    use_llm = (
        router.uses_llm(LLMTask.MATCH)
        and eligible
        and scores.overall >= settings.matching.notify_threshold - 0.1
    )
    explanation = await explain(
        router,
        use_llm=use_llm,
        job=job,
        extraction=extraction,
        scores=scores,
        coverage=coverage,
        checks=checks,
        hits=hits,
        eligible=eligible,
    )

    match = (
        await session.execute(
            select(JobMatch).where(JobMatch.user_id == user.id, JobMatch.job_id == job.id)
        )
    ).scalar_one_or_none()
    if match is None:
        match = JobMatch(user_id=user.id, profile_id=profile.id, job_id=job.id)
        session.add(match)
    match.profile_id = profile.id
    match.analysis_id = analysis.id
    match.profile_version = profile.version
    match.eligible = eligible
    match.eligibility = [c.as_dict() for c in checks]
    match.overall_score = scores.overall
    match.dimensions = {**scores.dimensions, "weights": scores.weights}
    match.strengths = explanation.strengths
    match.gaps = explanation.gaps
    match.concerns = explanation.concerns
    match.reasoning = explanation.reasoning
    match.requirement_coverage = [c.as_dict() for c in coverage]
    match.evidence = explanation.evidence
    match.scorer = SCORER_VERSION + (f"+{explanation.llm_model}" if explanation.llm_model else "")
    await session.flush()

    await session.execute(
        update(UserJob)
        .where(
            UserJob.user_id == user.id,
            UserJob.job_id == job.id,
            UserJob.status.in_((JobLifecycle.DISCOVERED, JobLifecycle.ANALYZED)),
        )
        .values(status=JobLifecycle.MATCHED, updated_at=now)
    )
    await emit(
        session,
        EventType.JOB_MATCHED,
        user_id=user.id,
        job_id=job.id,
        company_id=job.company_id,
        summary=f"{label_for(scores.overall, eligible)}: {job.title} at {job.company} ({round(scores.overall * 100)}%)",
        payload={"score": scores.overall, "eligible": eligible},
    )
    await _notify(session, user, job, match, settings.matching.high_match_threshold,
                  settings.matching.notify_threshold, settings.notifications.notify_new_jobs)  # fmt: skip
    return match


async def _notify(
    session: AsyncSession,
    user: User,
    job: Job,
    match: JobMatch,
    high_threshold: float,
    notify_threshold: float,
    notify_new_jobs: bool,
) -> None:
    if not match.eligible or not job.is_active:
        return
    top = match.strengths[0]["text"] if match.strengths else match.reasoning
    created = False
    if match.overall_score >= high_threshold:
        created = await notify(
            session,
            user_id=user.id,
            type=NotificationType.HIGH_MATCH,
            priority=NotificationPriority.HIGH,
            title=f"High match: {job.title} at {job.company}",
            body=top,
            job_id=job.id,
            action_url=f"/jobs/{job.id}",
            dedupe_key=f"high_match:{job.id}",
            data={"score": match.overall_score},
        )
    elif match.overall_score >= notify_threshold and notify_new_jobs:
        created = await notify(
            session,
            user_id=user.id,
            type=NotificationType.NEW_JOB,
            title=f"New match: {job.title} at {job.company}",
            body=top,
            job_id=job.id,
            action_url=f"/jobs/{job.id}",
            dedupe_key=f"new_job:{job.id}",
            data={"score": match.overall_score},
        )
    if created:
        await session.execute(
            update(UserJob)
            .where(
                UserJob.user_id == user.id,
                UserJob.job_id == job.id,
                UserJob.status == JobLifecycle.MATCHED,
            )
            .values(status=JobLifecycle.NOTIFIED, notified_at=utcnow())
        )
