"""Lever Postings API (public, official): api.lever.co/v0/postings/{company}."""

from __future__ import annotations

import html
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
    from careeros.discovery.adapters import LeverConfig


class LeverAdapter:
    complete_listing = True

    def __init__(self, config: LeverConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

    @property
    def base(self) -> str:
        host = "api.eu.lever.co" if self.config.region == "eu" else "api.lever.co"
        return f"https://{host}/v0/postings/{self.config.company}"

    @staticmethod
    def _description(posting: dict[str, Any]) -> str:
        parts = [posting.get("description") or ""]
        for block in posting.get("lists") or []:
            heading = html.escape(str(block.get("text") or ""))
            parts.append(f"<h3>{heading}</h3><ul>{block.get('content') or ''}</ul>")
        parts.append(posting.get("additional") or "")
        return "\n".join(p for p in parts if p)

    async def discover_jobs(self) -> list[RawJob]:
        company = self.config.company_name or title_from_slug(self.config.company)
        data = await self.http.get_json(self.base, params={"mode": "json"}, respect_robots=False)
        postings: list[dict[str, Any]] = data if isinstance(data, list) else []
        results: list[RawJob] = []
        for posting in postings:
            if not posting.get("id") or not posting.get("text"):
                continue
            categories = posting.get("categories") or {}
            location = categories.get("location")
            locations = categories.get("allLocations") or ([location] if location else [])
            salary_range = posting.get("salaryRange") or {}
            salary = None
            if salary_range:
                salary = SalaryHint(
                    minimum=as_float(salary_range.get("min")),
                    maximum=as_float(salary_range.get("max")),
                    currency=salary_range.get("currency"),
                    period=period_from_text(salary_range.get("interval")),
                )
            results.append(
                RawJob(
                    external_id=str(posting["id"]),
                    title=str(posting["text"]),
                    company=company,
                    url=posting.get("hostedUrl"),
                    apply_url=posting.get("applyUrl") or posting.get("hostedUrl"),
                    location=location,
                    locations=[str(loc) for loc in locations],
                    description_html=self._description(posting),
                    posted_at=parse_datetime(posting.get("createdAt")),
                    employment_type_hint=categories.get("commitment"),
                    remote_hint=posting.get("workplaceType"),
                    department=categories.get("team") or categories.get("department"),
                    salary=salary,
                    metadata={"company": self.config.company},
                )
            )
        return results
