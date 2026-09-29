from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from careeros.config import Settings
from careeros.core.enums import CompensationPeriod
from careeros.core.http import PoliteHttpClient
from careeros.discovery.adapters import build_adapter, validate_config
from careeros.discovery.models import SourceType
from careeros.discovery.normalize import normalize

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "http"


def _settings() -> Settings:
    return Settings(_env_file=None, http_min_host_interval_seconds=0, http_respect_robots_txt=False)  # type: ignore[call-arg]


async def _resolver(host: str) -> list[str]:
    return ["93.184.216.34"]


@pytest.fixture
def http() -> PoliteHttpClient:
    return PoliteHttpClient(_settings(), resolver=_resolver)


@respx.mock
async def test_greenhouse_adapter(http: PoliteHttpClient) -> None:
    respx.get("https://boards-api.greenhouse.io/v1/boards/examplecorp").mock(
        return_value=httpx.Response(200, json={"name": "Example Corp"})
    )
    respx.get("https://boards-api.greenhouse.io/v1/boards/examplecorp/jobs").mock(
        return_value=httpx.Response(
            200, text=(FIXTURES / "greenhouse_jobs.json").read_text("utf-8")
        )
    )
    adapter = build_adapter(SourceType.GREENHOUSE, {"board_token": "examplecorp"}, http)
    jobs = await adapter.discover_jobs()
    assert [j.title for j in jobs] == [
        "Software Engineer Intern, Platform",
        "Data Scientist (Remote)",
    ]
    assert jobs[0].company == "Example Corp"
    first = normalize(jobs[0])
    assert "Docker and Kubernetes" in first.description  # entity-escaped HTML decoded
    assert first.canonical_url == "https://boards.greenhouse.io/examplecorp/jobs/4012001"
    assert first.countries == ["India"]


@respx.mock
async def test_lever_adapter(http: PoliteHttpClient) -> None:
    respx.get("https://api.lever.co/v0/postings/examplelever").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "lever_postings.json").read_text("utf-8"))
    )
    adapter = build_adapter(
        SourceType.LEVER, {"company": "examplelever", "company_name": "Example Lever"}, http
    )
    [job] = await adapter.discover_jobs()
    assert job.company == "Example Lever"
    assert job.locations == ["Pune, India", "Mumbai, India"]
    assert job.salary is not None
    assert job.salary.period == CompensationPeriod.YEAR
    norm = normalize(job)
    assert "PostgreSQL" in norm.description
    assert norm.remote_type.value == "HYBRID"
    assert norm.canonical_url is not None
    assert "lever-source" not in norm.canonical_url


@respx.mock
async def test_ashby_adapter_skips_unlisted_roles(http: PoliteHttpClient) -> None:
    respx.get("https://api.ashbyhq.com/posting-api/job-board/exampleashby").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "ashby_board.json").read_text("utf-8"))
    )
    adapter = build_adapter(SourceType.ASHBY, {"organization": "exampleashby"}, http)
    jobs = await adapter.discover_jobs()
    assert [j.title for j in jobs] == ["Machine Learning Intern"]
    assert jobs[0].salary is not None
    assert jobs[0].salary.minimum == 50000
    assert normalize(jobs[0]).employment_type is not None


@respx.mock
async def test_career_page_json_ld(http: PoliteHttpClient) -> None:
    respx.get("https://careers.example-robotics.com/").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "career_page.html").read_text("utf-8"))
    )
    adapter = build_adapter(
        SourceType.CAREER_PAGE, {"url": "https://careers.example-robotics.com/"}, http
    )
    [job] = await adapter.discover_jobs()
    assert job.title == "Robotics Software Intern"
    assert job.company == "Example Robotics"
    assert job.url == "https://careers.example-robotics.com/careers/robotics-software-intern"
    assert job.deadline is not None
    assert job.salary is not None
    assert job.salary.period == CompensationPeriod.MONTH
    norm = normalize(job)
    assert norm.employment_type is not None
    assert norm.employment_type.value == "INTERNSHIP"


@respx.mock
async def test_rss_adapter(http: PoliteHttpClient) -> None:
    respx.get("https://research-jobs.example.edu/feed.xml").mock(
        return_value=httpx.Response(200, text=(FIXTURES / "jobs_feed.xml").read_text("utf-8"))
    )
    adapter = build_adapter(
        SourceType.RSS, {"url": "https://research-jobs.example.edu/feed.xml"}, http
    )
    [job] = await adapter.discover_jobs()
    assert job.company == "University Research Jobs"
    assert job.external_id == "ra-compbio-2026"
    assert job.posted_at is not None


def test_config_validation_and_identity() -> None:
    settings = _settings()
    _config, identity = validate_config(
        SourceType.GREENHOUSE, {"board_token": "ExampleCorp"}, settings
    )
    assert identity == "greenhouse:examplecorp"
    with pytest.raises(Exception, match="Invalid source configuration"):
        validate_config(SourceType.GREENHOUSE, {"board_token": "../../etc"}, settings)
    with pytest.raises(Exception, match="Invalid source configuration"):
        validate_config(SourceType.RSS, {"url": "file:///etc/passwd"}, settings)
    _, rss_identity = validate_config(
        SourceType.RSS, {"url": "https://Feeds.Example.com/jobs/?utm_source=x"}, settings
    )
    assert rss_identity == "rss:https://feeds.example.com/jobs"
