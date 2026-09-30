"""Running a source: fetch -> normalise -> filter -> de-duplicate -> store -> notify pipeline."""

from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import and_, exists, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.config import Settings
from careeros.core.clock import utcnow
from careeros.core.errors import CareerOSError, NotFoundError, SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.core.logging import get_logger
from careeros.discovery.adapters import build_adapter
from careeros.discovery.dedup import upsert_job
from careeros.discovery.models import CADENCE_INTERVALS, JobSource
from careeros.discovery.normalize import (
    NormalizedJob,
    extract_countries,
    normalize,
    normalize_company,
)
from careeros.discovery.raw import RawJob
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.jobs.models import Job, JobLifecycle, JobSourceLink, UserJob
from careeros.llm.types import Embedder
from careeros.profile.models import CareerPreferences, ProfessionalProfile

log = get_logger(__name__)

MAX_JOBS_PER_RUN = 500
_OPEN_STATES = (
    JobLifecycle.DISCOVERED,
    JobLifecycle.ANALYZED,
    JobLifecycle.MATCHED,
    JobLifecycle.NOTIFIED,
)


@dataclass(frozen=True, slots=True)
class Exclusions:
    companies: frozenset[str]
    keywords: tuple[re.Pattern[str], ...]

    def excludes(self, norm: NormalizedJob) -> str | None:
        if normalize_company(norm.company) in self.companies:
            return "excluded company"
        for pattern in self.keywords:
            if pattern.search(norm.title):
                return f"excluded keyword '{pattern.pattern[2:-2]}'"
        return None


async def load_exclusions(session: AsyncSession, user_id: uuid.UUID) -> Exclusions:
    prefs = (
        await session.execute(
            select(CareerPreferences)
            .join(ProfessionalProfile, ProfessionalProfile.id == CareerPreferences.profile_id)
            .where(ProfessionalProfile.user_id == user_id)
        )
    ).scalar_one_or_none()
    if prefs is None:
        return Exclusions(frozenset(), ())
    return Exclusions(
        companies=frozenset(normalize_company(c) for c in prefs.excluded_companies if c.strip()),
        keywords=tuple(
            re.compile(rf"\b{re.escape(k.strip())}\b", re.IGNORECASE)
            for k in prefs.excluded_keywords
            if k.strip()
        ),
    )


async def ensure_user_job(
    session: AsyncSession, *, user_id: uuid.UUID, job: Job, source: JobSource, now: datetime
) -> bool:
    """Attach the job to the user's inbox. Returns True if it is new for this user."""
    inserted = (
        await session.execute(
            pg_insert(UserJob)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                job_id=job.id,
                source_id=source.id,
                status=JobLifecycle.DISCOVERED,
                first_seen_at=now,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_nothing(index_elements=["user_id", "job_id"])
            .returning(UserJob.id)
        )
    ).scalar_one_or_none()
    if inserted is not None:
        return True
    # A re-opened posting comes back into the inbox.
    await session.execute(
        update(UserJob)
        .where(
            UserJob.user_id == user_id,
            UserJob.job_id == job.id,
            UserJob.status == JobLifecycle.CLOSED,
        )
        .values(status=JobLifecycle.DISCOVERED, updated_at=now)
    )
    return False


async def close_missing(
    session: AsyncSession, source: JobSource, seen_keys: set[str], now: datetime
) -> int:
    """Mark postings that vanished from a complete listing as closed."""
    stale = list(
        (
            await session.execute(
                select(JobSourceLink).where(
                    JobSourceLink.source_id == source.id, JobSourceLink.active.is_(True)
                )
            )
        ).scalars()
    )
    stale = [link for link in stale if link.external_id not in seen_keys]
    if not stale:
        return 0
    for link in stale:
        link.active = False
    await session.flush()
    job_ids = {link.job_id for link in stale}
    still_open = exists().where(
        and_(JobSourceLink.job_id == Job.id, JobSourceLink.active.is_(True))
    )
    closed_ids = list(
        (
            await session.execute(
                update(Job)
                .where(Job.id.in_(job_ids), Job.is_active.is_(True), ~still_open)
                .values(is_active=False, closed_at=now, updated_at=now)
                .returning(Job.id)
            )
        ).scalars()
    )
    if closed_ids:
        await session.execute(
            update(UserJob)
            .where(UserJob.job_id.in_(closed_ids), UserJob.status.in_(_OPEN_STATES))
            .values(status=JobLifecycle.CLOSED, updated_at=now)
        )
    return len(closed_ids)


def _record_success(source: JobSource, found: int, duration_ms: float, now: datetime) -> None:
    source.last_run_at = now
    source.last_success_at = now
    source.last_error = None
    source.last_jobs_found = found
    source.total_jobs_found = (source.total_jobs_found or 0) + found
    source.run_count = (source.run_count or 0) + 1
    source.consecutive_failures = 0
    previous = source.avg_duration_ms
    source.avg_duration_ms = duration_ms if previous is None else 0.8 * previous + 0.2 * duration_ms


def _record_failure(source: JobSource, error: CareerOSError, now: datetime) -> None:
    source.last_run_at = now
    source.last_failure_at = now
    source.last_error = error.message[:1000]
    source.run_count = (source.run_count or 0) + 1
    source.error_count = (source.error_count or 0) + 1
    source.consecutive_failures = (source.consecutive_failures or 0) + 1


def schedule_next(source: JobSource, now: datetime) -> None:
    interval = CADENCE_INTERVALS[source.cadence]
    source.next_run_at = now + interval if interval else None


def _within_regions(
    raws: list[RawJob], countries: list[str] | None, stats: Counter[str]
) -> list[RawJob]:
    """Keep jobs in the source's configured countries (global boards list the whole world)."""
    wanted = set(extract_countries(countries or []))
    if not wanted:
        return raws
    kept = []
    for raw in raws:
        found = set(extract_countries(raw.locations or ([raw.location] if raw.location else [])))
        if found and not found & wanted:
            stats["out_of_region"] += 1
            continue
        kept.append(raw)  # no stated country: let eligibility decide
    return kept


async def run_source(
    session: AsyncSession,
    source_id: uuid.UUID,
    *,
    settings: Settings,
    fetcher: PoliteHttpClient,
    embedder: Embedder | None = None,
) -> dict[str, int]:
    source = await session.get(JobSource, source_id)
    if source is None:
        raise NotFoundError("Job source not found")
    if not source.enabled:
        return {"skipped": 1}
    now = utcnow()
    started = time.perf_counter()
    adapter = build_adapter(source.type, source.config, fetcher)
    try:
        raws = await adapter.discover_jobs()
    except CareerOSError as exc:
        _record_failure(source, exc, now)
        schedule_next(source, now)
        await emit(
            session,
            EventType.DISCOVERY_FAILED,
            user_id=source.user_id,
            summary=f"{source.name}: discovery failed — {exc.message}",
            payload={"source_id": str(source.id), "error": exc.code},
        )
        await session.commit()  # keep the health record even when the task is retried
        if isinstance(exc, SourceFetchError) and exc.retryable:
            raise
        return {"failed": 1}

    exclusions = await load_exclusions(session, source.user_id)
    stats: Counter[str] = Counter(found=len(raws))
    raws = _within_regions(raws, source.config.get("countries"), stats)
    seen: set[str] = set()
    for raw in raws[:MAX_JOBS_PER_RUN]:
        try:
            async with session.begin_nested():
                norm = normalize(raw)
                external_key = (
                    norm.external_id or norm.canonical_url or f"hash:{norm.description_hash[:40]}"
                )
                seen.add(external_key)
                reason = exclusions.excludes(norm)
                if reason:
                    stats["filtered"] += 1
                    continue
                result = await upsert_job(
                    session,
                    norm,
                    source=source,
                    external_key=external_key,
                    now=now,
                    embedder=embedder,
                )
                stats["new_jobs" if result.created else "known_jobs"] += 1
                if result.reason not in ("new", "external_id"):
                    stats["duplicates"] += 1
                is_new_for_user = await ensure_user_job(
                    session, user_id=source.user_id, job=result.job, source=source, now=now
                )
                if is_new_for_user:
                    stats["new_for_user"] += 1
                    await emit(
                        session,
                        EventType.JOB_DISCOVERED,
                        user_id=source.user_id,
                        job_id=result.job.id,
                        company_id=result.job.company_id,
                        summary=f"Discovered {result.job.title} at {result.job.company}",
                        payload={"source_id": str(source.id), "dedup": result.reason},
                    )
                elif result.description_changed:
                    await emit(
                        session,
                        EventType.JOB_NORMALIZED,
                        user_id=source.user_id,
                        job_id=result.job.id,
                        summary=f"{result.job.title} at {result.job.company} was updated",
                        payload={"source_id": str(source.id)},
                    )
        except Exception as exc:  # one malformed posting must not sink the run
            stats["errors"] += 1
            log.warning("discovery_record_failed", source_id=str(source.id), error=str(exc)[:300])

    if adapter.complete_listing and stats["errors"] == 0 and len(raws) <= MAX_JOBS_PER_RUN:
        stats["closed"] = await close_missing(session, source, seen, now)

    duration_ms = (time.perf_counter() - started) * 1000
    _record_success(source, len(raws), duration_ms, now)
    schedule_next(source, now)
    summary = (
        f"{source.name}: {stats['found']} jobs found · {stats['new_for_user']} new"
        f" · {stats['duplicates']} duplicates merged"
        + (f" · {stats['filtered']} filtered by your preferences" if stats["filtered"] else "")
        + (f" · {stats['closed']} closed" if stats["closed"] else "")
    )
    await emit(
        session,
        EventType.DISCOVERY_COMPLETED,
        user_id=source.user_id,
        summary=summary,
        payload={"source_id": str(source.id), **stats, "duration_ms": round(duration_ms)},
    )
    log.info("discovery_completed", source_id=str(source.id), **stats)
    return dict(stats)
