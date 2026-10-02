"""Inbox queries: always scoped through the user's own `user_jobs` rows."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.companies.models import Company
from careeros.core.clock import utcnow
from careeros.core.errors import NotFoundError
from careeros.discovery.models import JobSource
from careeros.intelligence.extraction import JobExtraction
from careeros.intelligence.service import latest_analysis
from careeros.jobs.models import Job, JobLifecycle, JobSourceLink, UserJob
from careeros.jobs.schemas import (
    CompanyOut,
    EligibilityOut,
    JobCard,
    JobDetail,
    JobSort,
    JobView,
    MatchDetail,
    MatchSummary,
    Salary,
    SourceLinkOut,
)
from careeros.matching.explain import label_for
from careeros.matching.models import JobMatch
from careeros.profile.models import ProfessionalProfile

HIDDEN = (JobLifecycle.DISMISSED, JobLifecycle.CLOSED)
NEW_WINDOW = timedelta(days=7)
DEADLINE_WINDOW = timedelta(days=7)


def _summary(match: JobMatch) -> MatchSummary:
    dims = {k: float(v) for k, v in match.dimensions.items() if k != "weights"}
    return MatchSummary(
        overall_score=match.overall_score,
        eligible=match.eligible,
        label=label_for(match.overall_score, match.eligible),
        reasoning=match.reasoning,
        dimensions=dims,
        top_strengths=[s["text"] for s in match.strengths[:2]],
        top_gaps=[g["text"] for g in match.gaps[:2]],
        updated_at=match.updated_at,
    )


def to_card(
    user_job: UserJob, job: Job, match: JobMatch | None, source_name: str | None
) -> JobCard:
    salary = None
    if job.salary_min is not None or job.salary_max is not None:
        salary = Salary(
            minimum=job.salary_min,
            maximum=job.salary_max,
            currency=job.currency,
            period=job.salary_period,
        )
    return JobCard(
        job_id=job.id,
        title=job.title,
        company=job.company,
        company_id=job.company_id,
        location=job.location,
        countries=job.countries,
        remote_type=job.remote_type,
        employment_type=job.employment_type,
        seniority=job.seniority,
        posted_at=job.posted_at,
        deadline=job.deadline,
        first_seen_at=user_job.first_seen_at,
        application_platform=job.application_platform,
        application_url=job.application_url,
        is_active=job.is_active,
        status=user_job.status,
        salary=salary,
        source_name=source_name,
        match=_summary(match) if match is not None else None,
        application_stage=user_job.application_stage,
        applied_at=user_job.applied_at,
        follow_up_at=user_job.follow_up_at,
    )


def _base_query(user_id: uuid.UUID) -> Any:
    return (
        select(UserJob, Job, JobMatch, JobSource.name)
        .join(Job, Job.id == UserJob.job_id)
        .outerjoin(
            JobMatch, and_(JobMatch.user_id == UserJob.user_id, JobMatch.job_id == UserJob.job_id)
        )
        .outerjoin(JobSource, JobSource.id == UserJob.source_id)
        .where(UserJob.user_id == user_id)
    )


def apply_view(
    stmt: Select[Any], view: JobView, *, now: datetime, high_threshold: float
) -> Select[Any]:
    visible = and_(UserJob.status.not_in(HIDDEN), Job.is_active.is_(True))
    # Jobs appear once they are scored (seconds after discovery), so a role that is about to be
    # hidden as unsuitable never shows up unjudged.
    scored = JobMatch.id.is_not(None)
    if view == JobView.ALL:
        return stmt.where(visible, scored)
    if view == JobView.NEW:
        return stmt.where(
            UserJob.status.in_((JobLifecycle.MATCHED, JobLifecycle.NOTIFIED)),
            UserJob.first_seen_at >= now - NEW_WINDOW,
            Job.is_active.is_(True),
            scored,
        )  # fmt: skip
    if view == JobView.HIGH_MATCH:
        return stmt.where(
            visible, JobMatch.eligible.is_(True), JobMatch.overall_score >= high_threshold
        )
    if view == JobView.DEADLINE_SOON:
        return stmt.where(visible, Job.deadline > now, Job.deadline <= now + DEADLINE_WINDOW)
    if view == JobView.SAVED:
        return stmt.where(UserJob.status == JobLifecycle.SAVED)
    if view == JobView.DISMISSED:
        return stmt.where(UserJob.status == JobLifecycle.DISMISSED)
    if view == JobView.APPLIED:
        return stmt.where(UserJob.application_stage.is_not(None))
    if view == JobView.READY:
        return stmt.where(
            visible, UserJob.prepared_at.is_not(None), UserJob.application_stage.is_(None)
        )
    return stmt.where(or_(UserJob.status == JobLifecycle.CLOSED, Job.is_active.is_(False)))


async def list_jobs(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    view: JobView,
    sort: JobSort,
    query: str | None,
    limit: int,
    offset: int,
    high_threshold: float,
) -> tuple[list[JobCard], int]:
    now = utcnow()
    stmt = apply_view(_base_query(user_id), view, now=now, high_threshold=high_threshold)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(Job.title.ilike(like), Job.company.ilike(like), Job.location.ilike(like))
        )
    total = int(
        (
            await session.execute(select(func.count()).select_from(stmt.order_by(None).subquery()))
        ).scalar_one()
    )
    if sort == JobSort.SCORE:
        stmt = stmt.order_by(
            JobMatch.eligible.desc().nulls_last(),
            JobMatch.overall_score.desc().nulls_last(),
            UserJob.first_seen_at.desc(),
        )
    elif sort == JobSort.DEADLINE:
        stmt = stmt.order_by(
            Job.deadline.asc().nulls_last(), JobMatch.overall_score.desc().nulls_last()
        )
    else:
        stmt = stmt.order_by(UserJob.first_seen_at.desc(), Job.posted_at.desc().nulls_last())
    rows = (await session.execute(stmt.limit(limit).offset(offset))).all()
    return [to_card(uj, job, match, source_name) for uj, job, match, source_name in rows], total  # fmt: skip


async def get_user_job(session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> UserJob:
    user_job = (
        await session.execute(
            select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == job_id)
        )
    ).scalar_one_or_none()
    if user_job is None:
        raise NotFoundError("Job not found in your inbox")
    return user_job


async def job_detail(session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID) -> JobDetail:
    row = (await session.execute(_base_query(user_id).where(UserJob.job_id == job_id))).first()
    if row is None:
        raise NotFoundError("Job not found in your inbox")
    user_job, job, match, source_name = row
    analysis = await latest_analysis(session, job.id)
    links = (
        await session.execute(
            select(JobSourceLink, JobSource.name)
            .outerjoin(JobSource, JobSource.id == JobSourceLink.source_id)
            .where(
                JobSourceLink.job_id == job.id,
                or_(JobSource.user_id == user_id, JobSource.id.is_(None)),
            )
        )
    ).all()
    company = await session.get(Company, job.company_id) if job.company_id else None
    match_detail = None
    if match is not None:
        profile_version = (
            await session.execute(
                select(ProfessionalProfile.version).where(
                    ProfessionalProfile.id == match.profile_id
                )
            )
        ).scalar_one_or_none()
        summary = _summary(match)
        match_detail = MatchDetail(
            **summary.model_dump(),
            eligibility=[EligibilityOut(**c) for c in match.eligibility],
            strengths=match.strengths,
            gaps=match.gaps,
            concerns=match.concerns,
            requirement_coverage=match.requirement_coverage,
            evidence=match.evidence,
            profile_version=match.profile_version,
            scorer=match.scorer,
            stale=profile_version is not None and profile_version > match.profile_version,
        )
    return JobDetail(
        card=to_card(user_job, job, match, source_name),
        description=job.description,
        department=job.department,
        canonical_url=job.canonical_url,
        analysis=JobExtraction.model_validate(analysis.extraction) if analysis else None,
        analysis_extractor=analysis.extractor if analysis else None,
        match=match_detail,
        sources=[
            SourceLinkOut(
                source_type=link.source_type,
                source_name=name,
                url=link.url,
                active=link.active,
                first_seen_at=link.first_seen_at,
                last_seen_at=link.last_seen_at,
            )
            for link, name in links
        ],
        company=CompanyOut(
            id=company.id,
            name=company.name,
            website=company.website,
            industry=company.industry,
            description=company.description,
        )
        if company
        else None,
        note=user_job.note,
        dismiss_reason=user_job.dismiss_reason,
    )


async def view_counts(
    session: AsyncSession, user_id: uuid.UUID, *, high_threshold: float
) -> dict[str, int]:
    now = utcnow()
    counts: dict[str, int] = {}
    for view in (
        JobView.NEW,
        JobView.HIGH_MATCH,
        JobView.DEADLINE_SOON,
        JobView.SAVED,
        JobView.ALL,
        JobView.APPLIED,
        JobView.READY,
    ):
        stmt = apply_view(_base_query(user_id), view, now=now, high_threshold=high_threshold)
        counts[view.value.lower()] = int(
            (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        )
    return counts
