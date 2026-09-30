"""Recompute job countries with the current location parser and re-match jobs that changed.

    uv run python -m careeros.tools.refresh_locations

Needed after improving country detection: stored jobs keep the countries computed when they
were discovered, and eligibility rules (e.g. sponsorship-only countries) depend on them.
"""

from __future__ import annotations

import asyncio
import sys

from sqlalchemy import select

from careeros.config import get_settings
from careeros.db import registry  # noqa: F401 - load every model so relationships resolve
from careeros.db.session import Database
from careeros.discovery.normalize import extract_countries
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
                if merged == job.countries:
                    continue
                job.countries = merged
                changed += 1
                user_jobs = (
                    await session.execute(
                        select(UserJob).where(
                            UserJob.job_id == job.id, UserJob.status != JobLifecycle.DISMISSED
                        )
                    )
                ).scalars()
                for user_job in user_jobs:
                    await enqueue(
                        session,
                        TaskType.MATCH_JOB,
                        {"job_id": str(job.id), "user_id": str(user_job.user_id)},
                        user_id=user_job.user_id,
                        idempotency_key=f"match:{user_job.user_id}:{job.id}:countries:{'-'.join(merged)}",
                        priority=3,
                    )
                    queued += 1
            await session.commit()
    finally:
        await db.dispose()
    return changed, queued


def main() -> None:
    changed, queued = asyncio.run(_run())
    sys.stdout.write(f"Updated countries on {changed} jobs; queued {queued} re-matches.
")


if __name__ == "__main__":
    main()
