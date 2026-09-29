"""Job analysis: extraction (cached per description hash) + job embedding."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.config import LLMTask
from careeros.core.errors import LLMProviderError, NotFoundError
from careeros.core.logging import get_logger
from careeros.events.models import EventType
from careeros.events.service import emit
from careeros.intelligence.extraction import (
    EXTRACTION_VERSION,
    JobExtraction,
    heuristic_extract,
    llm_extract,
)
from careeros.intelligence.models import JobAnalysis
from careeros.jobs.models import AnalysisStatus, Job
from careeros.llm.router import LLMRouter

log = get_logger(__name__)


def job_embedding_text(job: Job, extraction: JobExtraction) -> str:
    parts = [
        job.title,
        job.company,
        f"Required: {', '.join(extraction.required_skills)}" if extraction.required_skills else "",
        f"Preferred: {', '.join(extraction.preferred_skills)}"
        if extraction.preferred_skills
        else "",
        "Responsibilities: " + "; ".join(extraction.responsibilities[:8])
        if extraction.responsibilities
        else "",
        job.description[:4000],
    ]
    return "\n".join(p for p in parts if p)


async def latest_analysis(session: AsyncSession, job_id: uuid.UUID) -> JobAnalysis | None:
    return (
        await session.execute(
            select(JobAnalysis)
            .where(JobAnalysis.job_id == job_id)
            .order_by(JobAnalysis.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def analyze_job(session: AsyncSession, job_id: uuid.UUID, router: LLMRouter) -> JobAnalysis:
    job = await session.get(Job, job_id)
    if job is None:
        raise NotFoundError("Job not found")
    cached = (
        await session.execute(
            select(JobAnalysis).where(
                JobAnalysis.job_id == job.id,
                JobAnalysis.description_hash == job.description_hash,
                JobAnalysis.version == EXTRACTION_VERSION,
            )
        )
    ).scalar_one_or_none()
    if cached is not None and job.analysis_status == AnalysisStatus.ANALYZED:
        return cached

    base = heuristic_extract(
        title=job.title,
        company=job.company,
        description=job.description,
        locations=job.locations or ([job.location] if job.location else []),
        employment_type=job.employment_type,
        seniority=job.seniority,
        remote_type=job.remote_type,
        application_platform=job.application_platform.value,
    )
    extraction, extractor, provider, model = base, "HEURISTIC", "local", "local-heuristic"
    if router.uses_llm(LLMTask.EXTRACTION) and job.description.strip():
        try:
            extraction = await llm_extract(router, base, job.description, job.canonical_url)
            extractor = "LLM"
            provider = router.provider_name(LLMTask.EXTRACTION)
            model = router.model_for(LLMTask.EXTRACTION)
        except LLMProviderError as exc:
            # Degrade gracefully: the deterministic extraction is still useful.
            log.warning("llm_extraction_failed_fallback", job_id=str(job.id), error=exc.message)
            extractor = "HEURISTIC_FALLBACK"

    if extraction.deadline and job.deadline is None:
        job.deadline = datetime.combine(extraction.deadline, time(23, 59), tzinfo=UTC)
    if extraction.salary and job.salary_min is None and extraction.salary.minimum:
        job.salary_min = extraction.salary.minimum
        job.salary_max = extraction.salary.maximum
        job.currency = extraction.salary.currency
        job.salary_period = extraction.salary.period

    embedder = router.embedder
    [vector] = await embedder.embed_documents([job_embedding_text(job, extraction)])
    job.embedding = vector
    job.embedding_model = embedder.model

    if cached is None:
        cached = JobAnalysis(
            job_id=job.id,
            description_hash=job.description_hash,
            version=EXTRACTION_VERSION,
            extractor=extractor,
            provider=provider,
            model=model,
            extraction=extraction.model_dump(mode="json"),
        )
        session.add(cached)
    else:
        cached.extraction = extraction.model_dump(mode="json")
        cached.extractor, cached.provider, cached.model = extractor, provider, model
    job.analysis_status = AnalysisStatus.ANALYZED
    await session.flush()
    await emit(
        session,
        EventType.JOB_ANALYZED,
        job_id=job.id,
        company_id=job.company_id,
        summary=f"Analysed {job.title} at {job.company} ({len(extraction.required_skills)} required skills)",
        payload={"analysis_id": str(cached.id), "extractor": extractor},
    )
    return cached
