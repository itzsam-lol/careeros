"""Ready-to-apply kits for fresher roles at the user's dream companies.

Every scheduler tick, eligible fresher roles at a dream company (preferences: "Dream companies")
that have no kit yet get a PREPARE_APPLICATION task: a résumé tailored to the role and a cover
letter, built from the verified profile only. The Apply Kit adds the copy-ready answers. Once a
batch is done the user gets one alert per role, or a single summary when several are ready at
once, so adding a company does not set off a burst of notifications.

Nothing is submitted anywhere: the user applies on the employer's site, and the application
stage stays theirs to set.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.core.errors import ValidationFailedError
from careeros.discovery.normalize import normalize_company
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.jobs.models import Job, JobLifecycle, UserJob
from careeros.matching.dream import wants_application_kit
from careeros.matching.models import JobMatch
from careeros.notifications.models import NotificationPriority, NotificationType
from careeros.notifications.service import notify
from careeros.profile.models import CareerPreferences, ProfessionalProfile
from careeros.resumes.models import DocumentKind, DocumentStatus, ResumeDocument
from careeros.resumes.service import DocumentOptions, build_document, request_document
from careeros.scheduled_jobs import periodic
from careeros.tasks.models import AgentTask, TaskStatus, TaskType
from careeros.tasks.queue import enqueue
from careeros.tasks.runtime import TaskContext, task_handler
from careeros.users.models import User

if TYPE_CHECKING:
    from careeros.container import Container

_OPEN = (JobLifecycle.MATCHED, JobLifecycle.NOTIFIED, JobLifecycle.SAVED)
PREPARE_PER_TICK = 10  # per user; the rest follow on the next ticks
ALERT_EACH_UP_TO = 3  # more ready roles than this at once get a single summary alert


async def _dream_companies(session: AsyncSession) -> dict[uuid.UUID, list[str]]:
    rows = (
        await session.execute(
            select(ProfessionalProfile.user_id, CareerPreferences.target_companies).join(
                CareerPreferences, CareerPreferences.profile_id == ProfessionalProfile.id
            )
        )
    ).all()
    return {
        user_id: [c for c in companies if c.strip()] for user_id, companies in rows if companies
    }


@periodic("prepare_dream_roles")
async def enqueue_kit_preparation(session: AsyncSession, container: Container) -> int:
    queued = 0
    for user_id, dream in (await _dream_companies(session)).items():
        # Cheap SQL prefilter on the first word of each name; the exact rule runs below.
        prefixes = {normalize_company(name).split()[0] for name in dream if normalize_company(name)}
        if not prefixes:
            continue
        rows = (
            await session.execute(
                select(Job, JobMatch)
                .join(UserJob, UserJob.job_id == Job.id)
                .join(
                    JobMatch,
                    and_(JobMatch.user_id == UserJob.user_id, JobMatch.job_id == UserJob.job_id),
                )
                .where(
                    UserJob.user_id == user_id,
                    UserJob.prepared_at.is_(None),
                    UserJob.application_stage.is_(None),
                    UserJob.status.in_(_OPEN),
                    Job.is_active.is_(True),
                    JobMatch.eligible.is_(True),
                    or_(*(Job.company.ilike(f"{prefix}%") for prefix in prefixes)),
                )
                .order_by(JobMatch.overall_score.desc())
            )
        ).all()
        count = 0
        for job, match in rows:
            if count >= PREPARE_PER_TICK:
                break
            if not wants_application_kit(job, match, dream):
                continue
            await enqueue(
                session,
                TaskType.PREPARE_APPLICATION,
                {"user_id": str(user_id), "job_id": str(job.id)},
                user_id=user_id,
                idempotency_key=f"prepare:{user_id}:{job.id}",
                priority=6,
            )
            count += 1
        queued += count
    return queued


async def _latest_documents(
    session: AsyncSession, user_id: uuid.UUID, job_id: uuid.UUID
) -> dict[DocumentKind, ResumeDocument]:
    documents = (
        await session.execute(
            select(ResumeDocument)
            .where(ResumeDocument.user_id == user_id, ResumeDocument.job_id == job_id)
            .order_by(ResumeDocument.created_at.desc())
        )
    ).scalars()
    latest: dict[DocumentKind, ResumeDocument] = {}
    for document in documents:
        latest.setdefault(document.kind, document)
    return latest


@task_handler(TaskType.PREPARE_APPLICATION)
async def handle_prepare_application(ctx: TaskContext) -> dict[str, Any]:
    user_id, job_id = ctx.uuid("user_id"), ctx.uuid("job_id")
    session = ctx.session
    user_job = (
        await session.execute(
            select(UserJob).where(UserJob.user_id == user_id, UserJob.job_id == job_id)
        )
    ).scalar_one_or_none()
    job = await session.get(Job, job_id)
    user = await session.get(User, user_id)
    if user_job is None or job is None or user is None:
        return {"skipped": "job or user gone"}
    if user_job.prepared_at or user_job.application_stage or not job.is_active:
        return {"skipped": "already prepared, applied or closed"}

    existing = await _latest_documents(session, user_id, job_id)
    result: dict[str, str] = {}
    for kind in (DocumentKind.RESUME, DocumentKind.COVER_LETTER):
        document = existing.get(kind)
        if document is None or document.status == DocumentStatus.FAILED:
            try:
                document = await request_document(
                    session, user, job_id=job_id, kind=kind, options=DocumentOptions(),
                    enqueue_build=False,
                )  # fmt: skip
            except ValidationFailedError:
                continue  # no master résumé yet; the letter and answers are still prepared
            document = await build_document(session, document.id, ctx.container, announce=False)
        result[kind.value] = document.status.value
    user_job.prepared_at = utcnow()
    await emit(
        session,
        EventType.APPLICATION_READY,
        user_id=user_id,
        job_id=job_id,
        company_id=job.company_id,
        summary=f"Application kit ready: {job.title} at {job.company}"[:500],
        payload=result,
    )
    await session.commit()
    return result


def _and(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _kit_summary(documents: dict[DocumentKind, ResumeDocument]) -> str:
    ready = {
        kind for kind, document in documents.items() if document.status == DocumentStatus.READY
    }
    if {DocumentKind.RESUME, DocumentKind.COVER_LETTER} <= ready:
        return "Your tailored résumé and cover letter are in the Apply Kit, with answers to copy."
    if DocumentKind.RESUME in ready:
        return "Your tailored résumé is in the Apply Kit, with answers to copy."
    if DocumentKind.COVER_LETTER in ready:
        return "Your cover letter and answers are in the Apply Kit; tailor your résumé there too."
    return "Answers to the usual application questions are in the Apply Kit."


async def _announce_one(
    session: AsyncSession, user_job: UserJob, job: Job, match: JobMatch
) -> None:
    documents = await _latest_documents(session, user_job.user_id, job.id)
    closes = f" Closes {job.deadline:%d %b}." if job.deadline else ""
    created = await notify(
        session,
        user_id=user_job.user_id,
        type=NotificationType.APPLICATION_READY,
        priority=NotificationPriority.HIGH,
        title=f"Ready to apply: {job.title} at {job.company}",
        body=f"{round(match.overall_score * 100)}% match. {_kit_summary(documents)}{closes}",
        job_id=job.id,
        action_url=f"/jobs/{job.id}",
        dedupe_key=f"ready:{job.id}",
        data={"apply_kit": True, "score": match.overall_score},
    )
    if created and user_job.status == JobLifecycle.MATCHED:
        user_job.status = JobLifecycle.NOTIFIED
        user_job.notified_at = utcnow()


async def _announce_batch(
    session: AsyncSession, user_id: uuid.UUID, ready: list[tuple[UserJob, Job, JobMatch]]
) -> None:
    companies = list(dict.fromkeys(job.company for _, job, _ in ready))
    titles = [job.title for _, job, _ in ready[:2]]
    more = f" and {len(ready) - 2} more" if len(ready) > 2 else ""
    await notify(
        session,
        user_id=user_id,
        type=NotificationType.APPLICATION_READY,
        priority=NotificationPriority.HIGH,
        title=f"{len(ready)} fresher roles ready to apply at {_and(companies[:3])}",
        body=f"{'; '.join(titles)}{more}. Each has a tailored application kit.",
        action_url="/jobs",
        dedupe_key=f"ready_batch:{user_id}:{utcnow():%Y%m%d%H%M}",
        data={"view": "READY", "count": len(ready)},
    )


@periodic("announce_ready_roles")
async def announce_ready_kits(session: AsyncSession, container: Container) -> int:
    rows = (
        await session.execute(
            select(UserJob, Job, JobMatch)
            .join(Job, Job.id == UserJob.job_id)
            .join(
                JobMatch,
                and_(JobMatch.user_id == UserJob.user_id, JobMatch.job_id == UserJob.job_id),
            )
            .where(UserJob.prepared_at.is_not(None), UserJob.ready_alerted_at.is_(None))
            .order_by(JobMatch.overall_score.desc())
        )
    ).all()
    by_user: dict[uuid.UUID, list[tuple[UserJob, Job, JobMatch]]] = defaultdict(list)
    for user_job, job, match in rows:
        by_user[user_job.user_id].append((user_job, job, match))
    alerts = 0
    now = utcnow()
    for user_id, items in by_user.items():
        busy = (
            await session.execute(
                select(
                    exists().where(
                        AgentTask.user_id == user_id,
                        AgentTask.type == TaskType.PREPARE_APPLICATION,
                        AgentTask.status.in_((TaskStatus.QUEUED, TaskStatus.RUNNING)),
                    )
                )
            )
        ).scalar_one()
        if busy:
            continue  # one announcement for the whole batch, once it is done
        ready = [
            (user_job, job, match)
            for user_job, job, match in items
            if user_job.application_stage is None and user_job.status in _OPEN and job.is_active
        ]
        if 0 < len(ready) <= ALERT_EACH_UP_TO:
            for user_job, job, match in ready:
                await _announce_one(session, user_job, job, match)
                alerts += 1
        elif ready:
            await _announce_batch(session, user_id, ready)
            alerts += 1
        for user_job, _, _ in items:
            user_job.ready_alerted_at = now
    return alerts
