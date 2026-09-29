"""Greenhouse Job Board API (public, official): boards-api.greenhouse.io."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters._common import parse_datetime, title_from_slug
from careeros.discovery.raw import RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import GreenhouseConfig

API = "https://boards-api.greenhouse.io/v1/boards"


class GreenhouseAdapter:
    complete_listing = True

    def __init__(self, config: GreenhouseConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

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
        data = await self.http.get_json(
            f"{API}/{self.config.board_token}/jobs",
            params={"content": "true"},
            respect_robots=False,
        )
        jobs: list[dict[str, Any]] = data.get("jobs", []) if isinstance(data, dict) else []
        results: list[RawJob] = []
        for item in jobs:
            if not item.get("id") or not item.get("title"):
                continue
            location = (item.get("location") or {}).get("name")
            offices = [o.get("name") for o in item.get("offices") or [] if o.get("name")]
            departments = [d.get("name") for d in item.get("departments") or [] if d.get("name")]
            results.append(
                RawJob(
                    external_id=str(item["id"]),
                    title=str(item["title"]),
                    company=company,
                    url=item.get("absolute_url"),
                    apply_url=item.get("absolute_url"),
                    location=location,
                    locations=[location] if location else offices,
                    description_html=item.get("content"),
                    posted_at=parse_datetime(item.get("first_published") or item.get("updated_at")),
                    department=departments[0] if departments else None,
                    metadata={
                        "requisition_id": item.get("requisition_id"),
                        "updated_at": item.get("updated_at"),
                        "board_token": self.config.board_token,
                    },
                )
            )
        return results
