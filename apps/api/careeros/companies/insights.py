"""Company insights for a job seeker, built from what CareerOS already knows.

Everything here is public or the user's own data: the company's open roles that discovery has
collected (where, at what level, which skills), the user's own matches there, a short public
summary from Wikipedia, and search links the user can open to find recruiters and alumni.
Nothing is scraped from LinkedIn; the links only open a search in the user's browser.
"""

from __future__ import annotations

import re
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from urllib.parse import quote, quote_plus

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.companies.models import Company
from careeros.core.clock import utcnow
from careeros.core.enums import SeniorityLevel
from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.core.logging import get_logger
from careeros.discovery.normalize import detect_seniority
from careeros.intelligence.functions import LABELS, title_functions
from careeros.intelligence.models import JobAnalysis
from careeros.jobs.models import Job, JobLifecycle, UserJob
from careeros.matching.models import JobMatch

log = get_logger(__name__)

WIKI_SEARCH = "https://en.wikipedia.org/w/api.php"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/page/summary/"
SUMMARY_TTL = timedelta(days=30)
# A page is about the employer only if Wikipedia describes it as an organisation.
_ORGANISATION = re.compile(
    r"\b(company|corporation|conglomerate|multinational|firm|bank|startup|start-up|"
    r"enterprise|manufacturer|retailer|airline|business|group|consultancy|provider|"
    r"platform|developer|publisher|exchange|insurer|organisation|organization)\b",
    re.IGNORECASE,
)
_ENTRY = {SeniorityLevel.INTERN, SeniorityLevel.ENTRY}
_HIDDEN = (JobLifecycle.DISMISSED, JobLifecycle.CLOSED)


@dataclass
class RoleCount:
    label: str
    count: int


@dataclass
class YourMatch:
    job_id: uuid.UUID
    title: str
    location: str | None
    score: float
    eligible: bool


@dataclass
class SearchLink:
    label: str
    url: str


@dataclass
class CompanyInsights:
    company_id: uuid.UUID
    name: str
    summary: str | None
    summary_source: str | None
    website: str | None
    open_roles: int
    entry_level_roles: int
    newest_posting: datetime | None
    by_country: list[RoleCount] = field(default_factory=list)
    by_level: list[RoleCount] = field(default_factory=list)
    by_function: list[RoleCount] = field(default_factory=list)
    top_cities: list[RoleCount] = field(default_factory=list)
    top_skills: list[RoleCount] = field(default_factory=list)
    sponsorship_roles: int = 0
    your_matches: list[YourMatch] = field(default_factory=list)
    people_searches: list[SearchLink] = field(default_factory=list)
    research_links: list[SearchLink] = field(default_factory=list)


def _city(location: str | None) -> str | None:
    if not location:
        return None
    parts = [p.strip() for p in re.split(r"[,;/|(]", location) if p.strip()]
    for part in parts:
        if len(part) > 3 and not re.fullmatch(
            r"(?i)remote|hybrid|on-?site|in-office|india|australia", part
        ):
            return part.title() if part.isupper() else part
    return None


def _top(counter: Counter[str], n: int) -> list[RoleCount]:
    return [RoleCount(label, count) for label, count in counter.most_common(n)]


async def _wikipedia_summary(http: PoliteHttpClient, name: str) -> tuple[str, str] | None:
    try:
        found = await http.get_json(
            WIKI_SEARCH,
            params={
                "action": "query",
                "list": "search",
                "srsearch": f"{name} company",
                "srlimit": 3,
                "format": "json",
            },
            respect_robots=False,  # the official API (robots.txt targets crawlers)
        )
        for hit in (found.get("query") or {}).get("search") or []:
            title = str(hit.get("title") or "")
            if name.split()[0].lower() not in title.lower():
                continue
            page = await http.get_json(
                WIKI_SUMMARY + quote(title.replace(" ", "_")), respect_robots=False
            )
            text = str(page.get("extract") or "")
            about = f"{page.get('description') or ''} {text[:300]}"
            if page.get("type") == "standard" and _ORGANISATION.search(about):
                url = ((page.get("content_urls") or {}).get("desktop") or {}).get("page")
                return text[:900], str(url or f"https://en.wikipedia.org/wiki/{quote(title)}")
    except (SourceFetchError, ValueError, AttributeError) as exc:
        log.info("company_summary_unavailable", company=name, error=str(exc)[:200])
    return None


async def ensure_summary(session: AsyncSession, company: Company, http: PoliteHttpClient) -> None:
    """Cache a short public description on the company (refreshed monthly)."""
    meta = dict(company.metadata_ or {})
    fetched = meta.get("summary_fetched_at")
    if fetched and utcnow() - datetime.fromisoformat(fetched) < SUMMARY_TTL:
        return
    summary = await _wikipedia_summary(http, company.name)
    meta["summary_fetched_at"] = utcnow().isoformat()
    if summary:
        company.description, meta["summary_source"] = summary
    company.metadata_ = meta
    await session.flush()


def _searches(name: str, institution: str | None, country: str) -> list[SearchLink]:
    people = "https://www.linkedin.com/search/results/people/?keywords="
    links = [
        SearchLink(
            "University recruiters", people + quote_plus(f"{name} university recruiter {country}")
        ),
        SearchLink(
            "Talent acquisition", people + quote_plus(f"{name} talent acquisition {country}")
        ),
        SearchLink("Engineers there", people + quote_plus(f"{name} software engineer {country}")),
    ]
    if institution:
        links.insert(
            0,
            SearchLink(f"Alumni from {institution}", people + quote_plus(f"{name} {institution}")),
        )
    return links


def _research(name: str) -> list[SearchLink]:
    google = "https://www.google.com/search?q="
    return [
        SearchLink(
            "Interview experiences", google + quote_plus(f"{name} interview experience fresher")
        ),
        SearchLink("Salaries for freshers", google + quote_plus(f"{name} fresher salary India")),
        SearchLink("Recent news", f"https://news.google.com/search?q={quote_plus(name)}"),
    ]


def _short_institution(name: str | None) -> str | None:
    if not name:
        return None
    match = re.search(r"\(([^)]+)\)", name)  # "Indraprastha Institute ... (IIIT-Delhi)"
    return match.group(1) if match else name


async def company_insights(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    company: Company,
    http: PoliteHttpClient,
    institution: str | None = None,
    home_country: str = "India",
) -> CompanyInsights:
    await ensure_summary(session, company, http)
    jobs = list(
        (
            await session.execute(
                select(Job).where(Job.company_id == company.id, Job.is_active.is_(True))
            )
        ).scalars()
    )
    job_ids = [job.id for job in jobs]
    countries: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    functions: Counter[str] = Counter()
    cities: Counter[str] = Counter()
    entry = 0
    for job in jobs:
        for country in job.countries or ["Not stated"]:
            countries[country] += 1
        level = job.seniority
        if level == SeniorityLevel.UNKNOWN:
            level = detect_seniority(job.title, job.employment_type)
        levels[level.value.title() if level != SeniorityLevel.UNKNOWN else "Not stated"] += 1
        entry += level in _ENTRY
        for function in title_functions(job.title):
            functions[LABELS[function].capitalize()] += 1
        city = _city(job.location)
        if city:
            cities[city] += 1

    skills: Counter[str] = Counter()
    sponsorship = 0
    if job_ids:
        analyses = (
            await session.execute(
                select(JobAnalysis.job_id, JobAnalysis.extraction)
                .where(JobAnalysis.job_id.in_(job_ids))
                .order_by(JobAnalysis.created_at)
            )
        ).all()
        # Ordered oldest first, so each job keeps its latest analysis.
        latest: dict[uuid.UUID, dict[str, Any]] = dict(analyses)
        by_id = {job.id: job for job in jobs}
        for job_id, extraction in latest.items():
            skills.update(dict.fromkeys(extraction.get("required_skills") or [], 1))
            if extraction.get("sponsorship") == "AVAILABLE" and "Australia" in (
                by_id[job_id].countries or []
            ):
                sponsorship += 1

    rows = (
        await session.execute(
            select(Job, JobMatch)
            .join(UserJob, UserJob.job_id == Job.id)
            .join(JobMatch, (JobMatch.job_id == Job.id) & (JobMatch.user_id == user_id))
            .where(
                UserJob.user_id == user_id,
                Job.company_id == company.id,
                Job.is_active.is_(True),
                UserJob.status.not_in(_HIDDEN),
            )
            .order_by(JobMatch.overall_score.desc())
            .limit(8)
        )
    ).all()
    meta = company.metadata_ or {}
    return CompanyInsights(
        company_id=company.id,
        name=company.name,
        summary=company.description,
        summary_source=meta.get("summary_source"),
        website=company.website,
        open_roles=len(jobs),
        entry_level_roles=entry,
        newest_posting=max((j.posted_at for j in jobs if j.posted_at), default=None),
        by_country=_top(countries, 6),
        by_level=_top(levels, 7),
        by_function=_top(functions, 6),
        top_cities=_top(cities, 6),
        top_skills=_top(skills, 12),
        sponsorship_roles=sponsorship,
        your_matches=[
            YourMatch(job.id, job.title, job.location, match.overall_score, match.eligible)
            for job, match in rows
        ],
        people_searches=_searches(company.name, _short_institution(institution), home_country),
        research_links=_research(company.name),
    )
