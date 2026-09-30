"""Workday career sites (public JSON behind every *.myworkdayjobs.com careers page).

Many large employers (Salesforce, Adobe, NVIDIA, Citi, Morgan Stanley, Telstra, ...) publish
their jobs this way. A site is identified by its careers URL, e.g.
https://adobe.wd5.myworkdayjobs.com/external_experienced. We narrow the listing to the
configured countries with the site's own country facet when it has one, otherwise with a
text search, and then fetch each posting's full description.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any
from urllib.parse import urlsplit

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import parse_datetime
from careeros.discovery.raw import RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import WorkdayConfig

_SITE = re.compile(
    r"^https://(?P<tenant>[a-z0-9-]+)\.(?P<wd>wd\d{1,3})\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?(?P<site>[A-Za-z0-9_-]+)",
)
PAGE = 20


def parse_site(url: str) -> tuple[str, str, str]:
    """(tenant, wdN, site) from a Workday careers URL."""
    match = _SITE.match(url.strip())
    if not match:
        raise ValueError(
            "Not a Workday careers URL (expected https://<company>.wd<N>.myworkdayjobs.com/<site>)"
        )
    return match.group("tenant"), match.group("wd"), match.group("site")


def _country_facets(facets: list[dict[str, Any]], countries: list[str]) -> dict[str, list[str]]:
    """Map the site's country facet parameter to the ids of the wanted countries."""
    wanted = {c.lower() for c in countries}
    found: dict[str, list[str]] = {}
    stack = [(f.get("facetParameter", ""), f) for f in facets or []]
    while stack:
        param, facet = stack.pop()
        for value in facet.get("values") or []:
            if "values" in value:
                stack.append((value.get("facetParameter", param), value))
                continue
            if "country" in param.lower() and (value.get("descriptor") or "").lower() in wanted:
                found.setdefault(param, []).append(str(value.get("id")))
    return found


class WorkdayAdapter:
    # The listing is filtered by country and capped, so absence does not mean a job closed.
    complete_listing = False

    def __init__(self, config: WorkdayConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http
        self.tenant, self.wd, self.site = parse_site(config.url)
        self.origin = f"https://{self.tenant}.{self.wd}.myworkdayjobs.com"
        self.api = f"{self.origin}/wday/cxs/{self.tenant}/{self.site}"

    async def _search(self, facets: dict[str, list[str]], text: str, offset: int) -> dict[str, Any]:
        body = {"appliedFacets": facets, "limit": PAGE, "offset": offset, "searchText": text}
        data = await self.http.post_json(f"{self.api}/jobs", body)
        return data if isinstance(data, dict) else {}

    async def _postings(self) -> list[dict[str, Any]]:
        first = await self._search({}, "", 0)
        facets = _country_facets(first.get("facets") or [], self.config.countries)
        queries: list[tuple[dict[str, list[str]], str]] = (
            [(facets, "")] if facets else [({}, country) for country in self.config.countries]
        )
        seen: dict[str, dict[str, Any]] = {}
        for applied, text in queries:
            offset = 0
            while len(seen) < self.config.max_jobs:
                page = await self._search(applied, text, offset)
                postings = page.get("jobPostings") or []
                for posting in postings:
                    path = posting.get("externalPath")
                    if path and path not in seen:
                        seen[path] = posting
                offset += PAGE
                if not postings or offset >= int(page.get("total") or 0):
                    break
        return list(seen.values())[: self.config.max_jobs]

    async def discover_jobs(self) -> list[RawJob]:
        company = self.config.company_name or self.tenant.replace("-", " ").title()
        results: list[RawJob] = []
        for posting in await self._postings():
            path = posting["externalPath"]
            try:
                detail = await self.http.get_json(f"{self.api}{path}", respect_robots=False)
            except SourceFetchError:
                continue  # one broken posting should not fail the whole run
            info = (detail or {}).get("jobPostingInfo") or {}
            title = info.get("title") or posting.get("title")
            if not title:
                continue
            locations = [
                loc
                for loc in [info.get("location"), *(info.get("additionalLocations") or [])]
                if loc
            ]
            url = info.get("externalUrl") or f"{self.origin}/{self.site}{path}"
            results.append(
                RawJob(
                    external_id=str(info.get("jobReqId") or info.get("id") or path),
                    title=str(title),
                    company=company,
                    url=url,
                    apply_url=url,
                    location=info.get("location") or posting.get("locationsText"),
                    locations=[str(loc) for loc in locations],
                    description_html=info.get("jobDescription") or "",
                    posted_at=parse_datetime(info.get("startDate")),
                    employment_type_hint=info.get("timeType"),
                    remote_hint=info.get("remoteType"),
                    metadata={
                        "workday": f"{self.tenant}/{self.site}",
                        "host": urlsplit(url).netloc,
                    },
                )
            )
        return results
