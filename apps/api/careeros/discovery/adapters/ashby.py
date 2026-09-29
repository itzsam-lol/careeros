"""Ashby public job board API (official): api.ashbyhq.com/posting-api/job-board/{org}."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import (
    as_float,
    parse_datetime,
    period_from_text,
    title_from_slug,
)
from careeros.discovery.raw import RawJob, SalaryHint

if TYPE_CHECKING:
    from careeros.discovery.adapters import AshbyConfig

API = "https://api.ashbyhq.com/posting-api/job-board"


def _salary(job: dict[str, Any]) -> SalaryHint | None:
    components = (job.get("compensation") or {}).get("summaryComponents") or []
    for component in components:
        if str(component.get("compensationType", "")).lower() == "salary":
            return SalaryHint(
                minimum=as_float(component.get("minValue")),
                maximum=as_float(component.get("maxValue")),
                currency=component.get("currencyCode"),
                period=period_from_text(component.get("interval")),
            )
    return None


class AshbyAdapter:
    complete_listing = True

    def __init__(self, config: AshbyConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

    async def discover_jobs(self) -> list[RawJob]:
        company = self.config.company_name or title_from_slug(self.config.organization)
        data = await self.http.get_json(
            f"{API}/{self.config.organization}",
            params={"includeCompensation": "true"},
            respect_robots=False,
        )
        jobs: list[dict[str, Any]] = data.get("jobs", []) if isinstance(data, dict) else []
        results: list[RawJob] = []
        for job in jobs:
            if job.get("isListed") is False or not job.get("id") or not job.get("title"):
                continue
            primary = job.get("location")
            secondary = [
                s.get("location") for s in job.get("secondaryLocations") or [] if s.get("location")
            ]
            remote = job.get("workplaceType") or ("Remote" if job.get("isRemote") else None)
            results.append(
                RawJob(
                    external_id=str(job["id"]),
                    title=str(job["title"]),
                    company=company,
                    url=job.get("jobUrl"),
                    apply_url=job.get("applyUrl") or job.get("jobUrl"),
                    location=primary,
                    locations=[loc for loc in [primary, *secondary] if loc],
                    description_html=job.get("descriptionHtml"),
                    description_text=job.get("descriptionPlain"),
                    posted_at=parse_datetime(job.get("publishedAt")),
                    employment_type_hint=job.get("employmentType"),
                    remote_hint=remote,
                    department=job.get("department") or job.get("team"),
                    salary=_salary(job),
                    metadata={"organization": self.config.organization},
                )
            )
        return results
