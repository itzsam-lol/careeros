"""RSS / Atom job feeds (many boards and university job pages publish one)."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import feedparser

from careeros.core.http import PoliteHttpClient
from careeros.discovery.raw import RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import RSSConfig


def _entry_time(entry: Any) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if not parsed:
        return None
    return datetime.fromtimestamp(calendar.timegm(parsed), tz=UTC)


class RSSAdapter:
    complete_listing = False

    def __init__(self, config: RSSConfig, http: PoliteHttpClient) -> None:
        self.config = config
        self.http = http

    async def discover_jobs(self) -> list[RawJob]:
        page = await self.http.get(self.config.url)
        feed = feedparser.parse(page.content)
        company = self.config.company_name or str(feed.feed.get("title") or "Unknown company")
        results: list[RawJob] = []
        for entry in feed.entries[:500]:
            title = entry.get("title")
            link = entry.get("link")
            if not title:
                continue
            content = entry.get("content")
            body = content[0].get("value") if content else entry.get("summary")
            results.append(
                RawJob(
                    external_id=str(entry.get("id") or link or title)[:200],
                    title=str(title),
                    company=company,
                    url=link,
                    apply_url=link,
                    description_html=body,
                    posted_at=_entry_time(entry),
                    metadata={"feed": self.config.url},
                )
            )
        return results
