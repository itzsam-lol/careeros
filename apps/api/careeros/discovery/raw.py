"""The adapter contract: every source produces `RawJob`s (spec §12)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from careeros.core.enums import CompensationPeriod


class SalaryHint(BaseModel):
    minimum: float | None = None
    maximum: float | None = None
    currency: str | None = None
    period: CompensationPeriod | None = None


class RawJob(BaseModel):
    external_id: str | None = None
    title: str
    company: str
    url: str | None = None
    apply_url: str | None = None
    location: str | None = None
    locations: list[str] = Field(default_factory=list)
    description_html: str | None = None
    description_text: str | None = None
    posted_at: datetime | None = None
    deadline: datetime | None = None
    employment_type_hint: str | None = None
    remote_hint: str | None = None
    department: str | None = None
    salary: SalaryHint | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class JobSourceAdapter(Protocol):
    #: True when a run returns the source's complete current listing, so jobs missing from a
    #: successful run can be marked closed. False for partial feeds (RSS, crawled pages).
    complete_listing: bool

    async def discover_jobs(self) -> list[RawJob]: ...
