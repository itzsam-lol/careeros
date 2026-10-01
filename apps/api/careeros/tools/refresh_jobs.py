"""Recompute derived job fields (countries, seniority, employment type) and re-match the jobs
that changed.

    uv run python -m careeros.tools.refresh_jobs

Needed after improving location or level detection: stored jobs keep the values computed when
they were discovered, and eligibility and scoring (e.g. sponsorship-only countries) use them.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from careeros.config import get_settings
from careeros.core.enums import EmploymentType
from careeros.db import registry  # noqa: F401 - load every model so relationships resolve
from careeros.db.session import Database
from careeros.discovery.normalize import (
    detect_employment_type,
    detect_seniority,
    extract_countries,
)
from careeros.jobs.models import Job, JobLifecycle, UserJob
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue


async def _run() -> tuple[int, int]:
    db = Database.from_settings(get_settings())
    changed = queued = 0
    try:
        async with db.session() as session:
            jobs = (await session.execute(select(Job))).scalars().all()
            for job in jobs:
                countries = extract_countries(
                    job.locations or ([job.location] if job.location else [])
                )
                merged = list(dict.fromkeys([*job.countries, *countries]))
                employment_type = job.employment_type
                if employment_type == EmploymentType.INTERNSHIP and (
                    detect_employment_type(job.title, None, job.description or "")
                    != EmploymentType.INTERNSHIP
                ):
                    # Marked an internship by a looser rule ("Internal", "mentor our interns").
                    # Cleared here; the next discovery run sets it again from the source's own
                    # employment type, if the posting gives one.
                    employment_type = None
                seniority = detect_seniority(job.title, employment_type)
                if (
                    merged == job.countries
                    and seniority == job.seniority
                    and employment_type == job.employment_type
                ):
                    continue
                job.countries = merged
                job.seniority = seniority
                job.employment_type = employment_type
                changed += 1
                user_jobs = (
                    await session.execute(
                        select(UserJob).where(
                            UserJob.job_id == job.id, UserJob.status != JobLifecycle.DISMISSED
                        )
                    )
                ).scalars()
                key = f"{'-'.join(merged)}:{seniority.value}"
                for user_job in user_jobs:
                    await enqueue(
                        session,
                        TaskType.MATCH_JOB,
                        {"job_id": str(job.id), "user_id": str(user_job.user_id)},
                        user_id=user_job.user_id,
                        idempotency_key=f"match:{user_job.user_id}:{job.id}:refresh:{key}"[:200],
                        priority=3,
                    )
                    queued += 1
            await session.commit()
    finally:
        await db.dispose()
    return changed, queued


def main() -> None:
    changed, queued = asyncio.run(_run())
    sys.stdout.write(f"Updated {changed} jobs; queued {queued} re-matches.\n")


if __name__ == "__main__":
    main()
