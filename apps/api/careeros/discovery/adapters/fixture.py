"""Local fixture feeds (fixtures/jobs/<name>.json) for development and tests."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from careeros.config import REPO_ROOT
from careeros.core.errors import SourceFetchError
from careeros.core.http import PoliteHttpClient
from careeros.discovery.raw import RawJob

if TYPE_CHECKING:
    from careeros.discovery.adapters import FixtureConfig

FIXTURE_DIR = REPO_ROOT / "fixtures" / "jobs"


class FixtureAdapter:
    complete_listing = True

    def __init__(self, config: FixtureConfig, http: PoliteHttpClient) -> None:
        self.config = config

    async def discover_jobs(self) -> list[RawJob]:
        path = FIXTURE_DIR / f"{self.config.name}.json"
        if not path.is_file():
            raise SourceFetchError(f"Unknown fixture feed '{self.config.name}'", retryable=False)
        payload: dict[str, Any] = json.loads(path.read_text("utf-8"))
        company = payload.get("company")
        jobs = []
        for item in payload.get("jobs", []):
            data = {"company": company, **item}
            jobs.append(RawJob.model_validate(data))
        return jobs
