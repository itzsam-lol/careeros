"""De-duplication (spec §15): one canonical job per real opportunity, with source mappings.

Checks run from strongest to weakest evidence:

1. same source + external id              (the same posting seen again)
2. canonical URL                           (the same posting from another source/user)
3. company/title/location key + same text  (reposted or mirrored)
4. same company + title, near-identical text (shingle Jaccard) - multi-location mirrors
5. same company + title, borderline text similarity -> embedding similarity (only then)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.companies.models import Company
from careeros.companies.service import get_or_create_company
from careeros.core.enums import RemoteType
from careeros.discovery.models import JobSource
from careeros.discovery.normalize import NormalizedJob, jaccard, normalize_company, shingles
from careeros.jobs.models import AnalysisStatus, Job, JobSourceLink
from careeros.llm.embeddings import cosine_similarity
from careeros.llm.types import Embedder

TEXT_DUPLICATE_THRESHOLD = 0.88
BORDERLINE_TEXT_THRESHOLD = 0.55
SEMANTIC_DUPLICATE_THRESHOLD = 0.97


@dataclass(frozen=True, slots=True)
class UpsertResult:
    job: Job
    created: bool
    reason: str
    description_changed: bool = False


async def _by_link(session: AsyncSession, source: JobSource, external_key: str) -> Job | None:
    stmt = (
        select(Job)
        .join(JobSourceLink, JobSourceLink.job_id == Job.id)
        .where(JobSourceLink.source_id == source.id, JobSourceLink.external_id == external_key)
    )
    return (await session.execute(stmt)).scalars().first()


async def find_duplicate(
    session: AsyncSession,
    norm: NormalizedJob,
    *,
    source: JobSource,
    external_key: str,
    embedder: Embedder | None,
) -> tuple[Job | None, str]:
    if (job := await _by_link(session, source, external_key)) is not None:
        return job, "external_id"
    if norm.canonical_url:
        stmt = select(Job).where(Job.canonical_url == norm.canonical_url)
        if (job := (await session.execute(stmt)).scalars().first()) is not None:
            return job, "canonical_url"
    same_key = list(
        (
            await session.execute(select(Job).where(Job.dedup_key == norm.dedup_key).limit(10))
        ).scalars()
    )
    for job in same_key:
        if job.description_hash == norm.description_hash:
            return job, "dedup_key"

    candidates = list(
        (
            await session.execute(
                select(Job)
                .join(Company, Company.id == Job.company_id)
                .where(
                    Company.normalized_name == normalize_company(norm.company),
                    Job.normalized_title == norm.normalized_title,
                    Job.is_active.is_(True),
                )
                .limit(20)
            )
        ).scalars()
    )
    if not candidates:
        return None, "new"
    new_shingles = shingles(norm.description)
    borderline: list[Job] = []
    for job in candidates:
        if job.description_hash == norm.description_hash:
            return job, "same_text"
        similarity = jaccard(new_shingles, shingles(job.description))
        if similarity >= TEXT_DUPLICATE_THRESHOLD:
            return job, "similar_text"
        if similarity >= BORDERLINE_TEXT_THRESHOLD:
            borderline.append(job)
    if borderline and embedder is not None and norm.description:
        vectors = await embedder.embed_documents(
            [norm.description[:8000], *(j.description[:8000] for j in borderline)]
        )
        for job, vector in zip(borderline, vectors[1:], strict=True):
            if cosine_similarity(vectors[0], vector) >= SEMANTIC_DUPLICATE_THRESHOLD:
                return job, "semantic"
    return None, "new"


def _merge(job: Job, norm: NormalizedJob, now: datetime) -> None:
    job.last_seen_at = now
    job.is_active = True
    job.closed_at = None
    job.locations = list(dict.fromkeys([*job.locations, *norm.locations]))[:20]
    job.countries = list(dict.fromkeys([*job.countries, *norm.countries]))
    if norm.posted_at and (job.posted_at is None or norm.posted_at < job.posted_at):
        job.posted_at = norm.posted_at
    job.deadline = job.deadline or norm.deadline
    job.application_url = job.application_url or norm.application_url
    job.employment_type = job.employment_type or norm.employment_type
    if job.remote_type == RemoteType.UNKNOWN:
        job.remote_type = norm.remote_type
    job.department = job.department or norm.department
    if job.salary_min is None and job.salary_max is None and (norm.salary_min or norm.salary_max):
        job.salary_min, job.salary_max = norm.salary_min, norm.salary_max
        job.currency, job.salary_period = norm.currency, norm.salary_period


async def upsert_job(
    session: AsyncSession,
    norm: NormalizedJob,
    *,
    source: JobSource,
    external_key: str,
    now: datetime,
    embedder: Embedder | None = None,
) -> UpsertResult:
    job, reason = await find_duplicate(
        session, norm, source=source, external_key=external_key, embedder=embedder
    )
    description_changed = False
    if job is None:
        company = await get_or_create_company(session, norm.company)
        job = Job(
            company_id=company.id,
            company=norm.company,
            title=norm.title,
            normalized_title=norm.normalized_title,
            location=norm.location,
            locations=norm.locations,
            normalized_location=norm.normalized_location,
            countries=norm.countries,
            employment_type=norm.employment_type,
            remote_type=norm.remote_type,
            seniority=norm.seniority,
            department=norm.department,
            description=norm.description,
            description_hash=norm.description_hash,
            posted_at=norm.posted_at,
            deadline=norm.deadline,
            salary_min=norm.salary_min,
            salary_max=norm.salary_max,
            currency=norm.currency,
            salary_period=norm.salary_period,
            canonical_url=norm.canonical_url,
            external_id=norm.external_id,
            source_id=source.id,
            application_url=norm.application_url,
            application_platform=norm.application_platform,
            raw_metadata=norm.raw_metadata,
            dedup_key=norm.dedup_key,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
            analysis_status=AnalysisStatus.PENDING,
        )
        session.add(job)
        await session.flush()
        created = True
    else:
        _merge(job, norm, now)
        if (
            reason == "external_id"
            and norm.description
            and job.description_hash != norm.description_hash
        ):
            # The same posting was edited: keep the new text and analyse it again.
            job.description = norm.description
            job.description_hash = norm.description_hash
            job.title = norm.title
            job.normalized_title = norm.normalized_title
            job.analysis_status = AnalysisStatus.PENDING
            description_changed = True
        created = False

    await session.execute(
        pg_insert(JobSourceLink)
        .values(
            id=uuid.uuid4(),
            job_id=job.id,
            source_id=source.id,
            source_type=source.type.value,
            external_id=external_key,
            url=norm.canonical_url or norm.application_url,
            active=True,
            first_seen_at=now,
            last_seen_at=now,
        )
        .on_conflict_do_update(
            index_elements=["source_id", "external_id"],
            set_={"last_seen_at": now, "active": True, "job_id": job.id},
        )
    )
    return UpsertResult(
        job=job, created=created, reason=reason, description_changed=description_changed
    )
