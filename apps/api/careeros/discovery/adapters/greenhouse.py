"""Greenhouse Job Board API (public, official): boards-api.greenhouse.io."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import (
    BOARD_API_MAX_BYTES,
    parse_datetime,
    title_from_slug,
)
from careeros.discovery.normalize import extract_countries
from careeros.discovery.raw import KnownPostings, RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import GreenhouseConfig

API = "https://boards-api.greenhouse.io/v1/boards"
LARGE_BOARD_DETAILS = 60
_WORK_MODE = re.compile(
    r"(?:hybrid|remote|distributed|in-office|in office|on-?site|flexible)"
    r"(?:\s*(?:[;/,]|\bor\b|\band\b)\s*(?:hybrid|remote|distributed|in-office|in office|on-?site|flexible))*",
    re.IGNORECASE,
)


class GreenhouseAdapter:
    complete_listing = True

    def __init__(self, config: GreenhouseConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http
        self.known = KnownPostings()

    async def _company_name(self) -> str:
        if self.config.company_name:
            return self.config.company_name
        try:
            board = await self.http.get_json(
                f"{API}/{self.config.board_token}", respect_robots=False
            )
            name = board.get("name") if isinstance(board, dict) else None
        except SourceFetchError:
            name = None
        return str(name) if name else title_from_slug(self.config.board_token)

    async def discover_jobs(self) -> list[RawJob]:
        company = await self._company_name()
        try:
            data = await self.http.get_json(
                f"{API}/{self.config.board_token}/jobs",
                params={"content": "true"},
                respect_robots=False,
                max_bytes=BOARD_API_MAX_BYTES,
            )
        except SourceFetchError as exc:
            if "too large" not in exc.message:
                raise
            return await self._large_board(company)
        jobs: list[dict[str, Any]] = data.get("jobs", []) if isinstance(data, dict) else []
        return [self._raw(item, company) for item in jobs if item.get("id") and item.get("title")]

    async def _large_board(self, company: str) -> list[RawJob]:
        """Boards too big to download with descriptions (Anduril: 2,400 postings, 40+ MB).

        Take the light listing, keep postings in the source's countries, and fetch descriptions
        only for new ones. Known postings are still returned (without a description, which never
        overwrites a stored one) so the listing stays complete.
        """
        data = await self.http.get_json(
            f"{API}/{self.config.board_token}/jobs",
            respect_robots=False,
            max_bytes=BOARD_API_MAX_BYTES,
        )
        wanted = set(extract_countries(self.config.countries or []))
        details_left = LARGE_BOARD_DETAILS
        results: list[RawJob] = []
        for item in data.get("jobs", []) if isinstance(data, dict) else []:
            if not item.get("id") or not item.get("title"):
                continue
            found = set(extract_countries(_places(item)))
            if wanted and found and not found & wanted:
                continue
            if str(item["id"]) not in self.known.ids and details_left > 0:
                details_left -= 1
                try:
                    detail = await self.http.get_json(
                        f"{API}/{self.config.board_token}/jobs/{item['id']}", respect_robots=False
                    )
                    if isinstance(detail, dict):
                        item = {**item, **detail}
                except SourceFetchError:
                    pass  # listed without a description; the next run retries
            results.append(self._raw(item, company))
        return results

    def _raw(self, item: dict[str, Any], company: str) -> RawJob:
        location = (item.get("location") or {}).get("name")
        offices = [o.get("name") for o in item.get("offices") or [] if o.get("name")]
        # Some boards (Cloudflare) put the work mode in `location` ("Hybrid", "Distributed")
        # and the cities in `offices`; both are needed to know the country.
        if location and offices and _WORK_MODE.fullmatch(location.strip()):
            location = f"{'; '.join(offices[:3])} ({location.strip()})"
        departments = [d.get("name") for d in item.get("departments") or [] if d.get("name")]
        return RawJob(
            external_id=str(item["id"]),
            title=str(item["title"]),
            company=company,
            url=item.get("absolute_url"),
            apply_url=item.get("absolute_url"),
            location=location,
            locations=list(dict.fromkeys(p for p in [location, *offices] if p)),
            description_html=item.get("content"),
            posted_at=parse_datetime(item.get("first_published") or item.get("updated_at")),
            department=departments[0] if departments else None,
            metadata={
                "requisition_id": item.get("requisition_id"),
                "updated_at": item.get("updated_at"),
                "board_token": self.config.board_token,
            },
        )


def _places(item: dict[str, Any]) -> list[str]:
    location = (item.get("location") or {}).get("name")
    offices = [o.get("name") for o in item.get("offices") or [] if o.get("name")]
    return [str(p) for p in [location, *offices] if p]
