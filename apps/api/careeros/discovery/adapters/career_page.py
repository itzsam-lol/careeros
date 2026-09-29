"""Company career pages that embed schema.org JobPosting JSON-LD (common and machine-readable)."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.core.logging import get_logger
from careeros.discovery.adapters._common import as_float, parse_datetime, period_from_text
from careeros.discovery.raw import RawJob, SalaryHint

if TYPE_CHECKING:
    from careeros.discovery.adapters import CareerPageConfig

log = get_logger(__name__)


def _walk(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, list):
        for item in node:
            yield from _walk(item)
    elif isinstance(node, dict):
        types = node.get("@type")
        type_list = types if isinstance(types, list) else [types]
        if "JobPosting" in type_list:
            yield node
        for key in ("@graph", "itemListElement", "item"):
            if key in node:
                yield from _walk(node[key])


def _text(value: Any) -> str | None:
    if isinstance(value, dict):
        return _text(value.get("name") or value.get("@value"))
    if isinstance(value, list):
        return _text(value[0]) if value else None
    return str(value).strip() or None if value is not None else None


def _locations(posting: dict[str, Any]) -> list[str]:
    raw = posting.get("jobLocation")
    places = raw if isinstance(raw, list) else [raw] if raw else []
    results: list[str] = []
    for place in places:
        address = (place or {}).get("address") if isinstance(place, dict) else None
        if isinstance(address, str):
            results.append(address)
        elif isinstance(address, dict):
            parts = [
                _text(address.get(k))
                for k in ("addressLocality", "addressRegion", "addressCountry")
            ]
            joined = ", ".join(p for p in parts if p)
            if joined:
                results.append(joined)
    return results


def _salary(posting: dict[str, Any]) -> SalaryHint | None:
    base = posting.get("baseSalary")
    if not isinstance(base, dict):
        return None
    value = base.get("value")
    if isinstance(value, dict):
        minimum = as_float(value.get("minValue") or value.get("value"))
        maximum = as_float(value.get("maxValue") or value.get("value"))
        unit = value.get("unitText")
    else:
        minimum = maximum = as_float(value)
        unit = None
    return SalaryHint(
        minimum=minimum,
        maximum=maximum,
        currency=base.get("currency"),
        period=period_from_text(unit),
    )


def extract_job_postings(
    markup: str, *, page_url: str, fallback_company: str | None
) -> list[RawJob]:
    soup = BeautifulSoup(markup, "lxml")
    results: list[RawJob] = []
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(script.string or script.get_text() or "")
        except ValueError:
            continue
        for posting in _walk(data):
            title = _text(posting.get("title"))
            if not title:
                continue
            org = posting.get("hiringOrganization")
            company = (
                _text(org) or fallback_company or urlsplit(page_url).hostname or "Unknown company"
            )
            identifier = posting.get("identifier")
            external = _text(
                identifier.get("value") if isinstance(identifier, dict) else identifier
            )
            url = _text(posting.get("url")) or page_url
            employment = posting.get("employmentType")
            locations = _locations(posting)
            results.append(
                RawJob(
                    external_id=(external or url)[:200],
                    title=title,
                    company=company,
                    url=urljoin(page_url, url),
                    apply_url=urljoin(page_url, url),
                    location=locations[0] if locations else None,
                    locations=locations,
                    description_html=str(posting.get("description") or ""),
                    posted_at=parse_datetime(posting.get("datePosted")),
                    deadline=parse_datetime(posting.get("validThrough")),
                    employment_type_hint=" ".join(employment)
                    if isinstance(employment, list)
                    else _text(employment),
                    remote_hint="remote"
                    if str(posting.get("jobLocationType", "")).upper() == "TELECOMMUTE"
                    else None,
                    salary=_salary(posting),
                    metadata={"page": page_url},
                )
            )
    return results


def candidate_links(markup: str, *, page_url: str, pattern: str | None, limit: int) -> list[str]:
    soup = BeautifulSoup(markup, "lxml")
    host = urlsplit(page_url).hostname
    regex = (
        re.compile(pattern)
        if pattern
        else re.compile(r"/(jobs?|careers?|positions?|openings?)/", re.I)
    )
    links: dict[str, None] = {}
    for anchor in soup.find_all("a", href=True):
        href = urljoin(page_url, str(anchor["href"]).strip())
        parts = urlsplit(href)
        if parts.scheme not in ("http", "https") or parts.hostname != host:
            continue
        if href.split("#")[0] == page_url.split("#")[0] or not regex.search(parts.path):
            continue
        links.setdefault(href.split("#")[0], None)
        if len(links) >= limit:
            break
    return list(links)


class CareerPageAdapter:
    complete_listing = False

    def __init__(self, config: CareerPageConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

    async def discover_jobs(self) -> list[RawJob]:
        first = await self.http.get(self.config.url)
        jobs = extract_job_postings(
            first.text, page_url=first.url, fallback_company=self.config.company_name
        )
        if self.config.follow_links:
            for link in candidate_links(
                first.text,
                page_url=first.url,
                pattern=self.config.link_pattern,
                limit=self.config.max_pages,
            ):
                try:
                    page = await self.http.get(link)
                except SourceFetchError as exc:
                    log.info("career_page_link_skipped", url=link, error=exc.message)
                    continue
                jobs.extend(
                    extract_job_postings(
                        page.text, page_url=page.url, fallback_company=self.config.company_name
                    )
                )
        if self.config.company_name:
            for job in jobs:
                job.company = self.config.company_name
        return jobs
