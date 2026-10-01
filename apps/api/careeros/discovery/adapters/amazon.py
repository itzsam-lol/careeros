"""Amazon jobs: the public search JSON behind amazon.jobs (robots.txt allows it).

Amazon runs its own ATS, so it is not on Greenhouse/Workday. The search is filtered by country
and job category, newest first; each result already carries the description and
qualifications, so no per-posting requests are needed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import parse_datetime
from careeros.discovery.raw import RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import AmazonConfig

API = "https://www.amazon.jobs/en/search.json"
SITE = "https://www.amazon.jobs"
_PAGE = 100
ISO3 = {
    "india": "IND", "australia": "AUS", "singapore": "SGP", "united states": "USA",
    "united kingdom": "GBR", "canada": "CAN", "germany": "DEU", "ireland": "IRL",
    "japan": "JPN", "united arab emirates": "ARE", "new zealand": "NZL",
}  # fmt: skip


def _section(title: str, html: str | None) -> str:
    return f"<h3>{title}</h3>{html}" if html else ""


class AmazonAdapter:
    # Newest postings only, capped per run: a missing posting has not necessarily closed.
    complete_listing = False

    def __init__(self, config: AmazonConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

    async def _page(self, country_code: str, offset: int) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "normalized_country_code[]": country_code,
            "result_limit": _PAGE,
            "offset": offset,
            "sort": "recent",
        }
        if self.config.categories:
            params["category[]"] = list(self.config.categories)
        data = await self.http.get_json(API, params=params)
        jobs = data.get("jobs") if isinstance(data, dict) else None
        return jobs if isinstance(jobs, list) else []

    async def discover_jobs(self) -> list[RawJob]:
        results: list[RawJob] = []
        seen: set[str] = set()
        for country in self.config.countries:
            code = ISO3.get(country.strip().lower())
            if code is None:
                continue
            offset = 0
            while offset < self.config.max_jobs:
                jobs = await self._page(code, offset)
                for job in jobs:
                    raw = self._raw(job)
                    if raw is not None and raw.external_id not in seen:
                        seen.add(raw.external_id or "")
                        results.append(raw)
                if len(jobs) < _PAGE:
                    break
                offset += _PAGE
        return results

    def _raw(self, job: dict[str, Any]) -> RawJob | None:
        job_id = job.get("id_icims") or job.get("id")
        title = job.get("title")
        if not job_id or not title:
            return None
        url = f"{SITE}{job['job_path']}" if job.get("job_path") else None
        description = "".join(
            [
                str(job.get("description") or ""),
                _section("Basic qualifications", job.get("basic_qualifications")),
                _section("Preferred qualifications", job.get("preferred_qualifications")),
            ]
        )
        locations = [str(p) for p in (job.get("location"), job.get("normalized_location")) if p]
        return RawJob(
            external_id=str(job_id),
            title=str(title),
            company=self.config.company_name,
            url=url,
            apply_url=job.get("url_next_step") or url,
            location=locations[0] if locations else None,
            locations=locations,
            description_html=description,
            posted_at=parse_datetime(job.get("posted_date")),
            employment_type_hint="internship"
            if job.get("is_intern")
            else job.get("job_schedule_type"),
            department=job.get("job_category"),
            metadata={
                "university_job": bool(job.get("university_job")),
                "business_category": job.get("business_category"),
            },
        )
