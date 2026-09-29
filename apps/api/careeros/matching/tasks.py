"""MATCH_JOB handler and periodic producers (stale re-matching, missing matches, deadlines)."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.jobs.models import AnalysisStatus, Job, JobLifecycle, UserJob
from careeros.matching.models import JobMatch
from careeros.matching.service import match_job
from careeros.notifications.models import NotificationPriority, NotificationType
from careeros.notifications.service import notify
from careeros.profile.models import ProfessionalProfile
from careeros.scheduled_jobs import periodic
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue
from careeros.tasks.runtime import TaskContext, task_handler
from careeros.users.models import User
from careeros.users.service import read_settings

if TYPE_CHECKING:
    from careeros.container import Container

_OPEN = (
    JobLifecycle.DISCOVERED,
    JobLifecycle.ANALYZED,
    JobLifecycle.MATCHED,
    JobLifecycle.NOTIFIED,
    JobLifecycle.SAVED,
)


@task_handler(TaskType.MATCH_JOB)
async def handle_match_job(ctx: TaskContext) -> dict[str, Any]:
    match = await match_job(
        ctx.session, user_id=ctx.uuid("user_id"), job_id=ctx.uuid("job_id"), container=ctx.container
    )
    if match is None:
        return {"skipped": "profile or analysis not ready"}
    return {"score": match.overall_score, "eligible": match.eligible}


@periodic("rematch_stale")
async def enqueue_stale_matches(session: AsyncSession, container: Container) -> int:
    """Profiles change; matches computed against an older profile version are refreshed."""
    rows = (
        await session.execute(
            select(JobMatch.user_id, JobMatch.job_id, ProfessionalProfile.version)
            .join(ProfessionalProfile, ProfessionalProfile.id == JobMatch.profile_id)
            .join(
                UserJob,
                and_(UserJob.user_id == JobMatch.user_id, UserJob.job_id == JobMatch.job_id),
            )
            .where(
                JobMatch.profile_version < ProfessionalProfile.version, UserJob.status.in_(_OPEN)
            )
            .limit(50)
        )
    ).all()
    for user_id, job_id, version in rows:
        await enqueue(
            session,
            TaskType.MATCH_JOB,
            {"job_id": str(job_id), "user_id": str(user_id)},
            user_id=user_id,
            idempotency_key=f"match:{user_id}:{job_id}:v{version}",
        )
    return len(rows)


@periodic("match_missing")
async def enqueue_missing_matches(session: AsyncSession, container: Container) -> int:
    """Jobs discovered before the profile existed still get matched once it does."""
    rows = (
        await session.execute(
            select(UserJob.user_id, UserJob.job_id, ProfessionalProfile.version)
            .join(Job, Job.id == UserJob.job_id)
            .join(ProfessionalProfile, ProfessionalProfile.user_id == UserJob.user_id)
            .where(
                Job.analysis_status == AnalysisStatus.ANALYZED,
                UserJob.status.in_((JobLifecycle.DISCOVERED, JobLifecycle.ANALYZED)),
                ~exists().where(
                    and_(JobMatch.user_id == UserJob.user_id, JobMatch.job_id == UserJob.job_id)
                ),
            )
            .limit(100)
        )
    ).all()
    for user_id, job_id, version in rows:
        await enqueue(
            session,
            TaskType.MATCH_JOB,
            {"job_id": str(job_id), "user_id": str(user_id)},
            user_id=user_id,
            idempotency_key=f"match:{user_id}:{job_id}:v{version}",
        )
    return len(rows)


@periodic("deadline_alerts")
async def create_deadline_alerts(session: AsyncSession, container: Container) -> int:
    """DEADLINE_SOON for saved jobs and eligible matches whose deadline is approaching."""
    now = utcnow()
    horizon = now + timedelta(days=30)
    rows = (
        await session.execute(
            select(UserJob, Job, JobMatch, User)
            .join(Job, Job.id == UserJob.job_id)
            .join(User, User.id == UserJob.user_id)
            .outerjoin(
                JobMatch,
                and_(JobMatch.user_id == UserJob.user_id, JobMatch.job_id == UserJob.job_id),
            )
            .where(
                Job.deadline.is_not(None),
                Job.deadline > now,
                Job.deadline < horizon,
                Job.is_active.is_(True),
                UserJob.status.in_(_OPEN),
            )
            .limit(500)
        )
    ).all()
    created = 0
    for user_job, job, match, user in rows:
        settings = read_settings(user)
        window = timedelta(hours=settings.notifications.deadline_warning_hours)
        wanted = user_job.status == JobLifecycle.SAVED or (
            match is not None
            and match.eligible
            and match.overall_score >= settings.matching.notify_threshold
        )
        if not wanted or job.deadline is None or job.deadline - now > window:
            continue
        hours = max(1, int((job.deadline - now).total_seconds() // 3600))
        when = f"{hours} hours" if hours < 48 else f"{hours // 24} days"
        if await notify(
            session,
            user_id=user.id,
            type=NotificationType.DEADLINE_SOON,
            priority=NotificationPriority.URGENT if hours < 24 else NotificationPriority.HIGH,
            title=f"Deadline in {when}: {job.title} at {job.company}",
            body=f"Applications close on {job.deadline:%d %b %Y, %H:%M} UTC.",
            job_id=job.id,
            action_url=f"/jobs/{job.id}",
            dedupe_key=f"deadline:{job.id}",
        ):
            created += 1
    return created
