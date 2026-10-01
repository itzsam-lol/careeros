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
from careeros.discovery.raw import KnownPostings

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
async def test_greenhouse_work_mode_locations_use_offices(http: PoliteHttpClient) -> None:
    """Cloudflare-style boards: `location` is "Hybrid", the cities are in `offices`."""
    job = {
        "id": 1,
        "title": "Software Engineer",
        "absolute_url": "https://boards.greenhouse.io/modecorp/jobs/1",
        "location": {"name": "Hybrid"},
        "offices": [{"name": "Austin, TX"}, {"name": "New York, NY"}],
        "content": "<p>Build things.</p>",
    }
    respx.get("https://boards-api.greenhouse.io/v1/boards/modecorp/jobs").mock(
        return_value=httpx.Response(200, json={"jobs": [job]})
    )
    adapter = build_adapter(
        SourceType.GREENHOUSE, {"board_token": "modecorp", "company_name": "Mode"}, http
    )
    [raw] = await adapter.discover_jobs()
    assert raw.location == "Austin, TX; New York, NY (Hybrid)"
    assert normalize(raw).countries == ["United States"]


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


@respx.mock
async def test_workday_adapter_uses_country_facets(http: PoliteHttpClient) -> None:
    api = "https://examplecorp.wd5.myworkdayjobs.com/wday/cxs/examplecorp/Careers"
    facets = [
        {
            "facetParameter": "locationCountry",
            "values": [
                {"descriptor": "India", "id": "in-id", "count": 1},
                {"descriptor": "Germany", "id": "de-id", "count": 9},
            ],
        }
    ]
    searches: list[dict[str, object]] = []

    def search(request: httpx.Request) -> httpx.Response:
        import json

        body = json.loads(request.content)
        searches.append(body)
        if not body["appliedFacets"]:
            return httpx.Response(200, json={"total": 10, "facets": facets, "jobPostings": []})
        return httpx.Response(
            200,
            json={
                "total": 1,
                "jobPostings": [
                    {
                        "title": "Data Analyst",
                        "externalPath": "/job/Pune/Data-Analyst_R1",
                        "locationsText": "Pune, India",
                    }
                ],
            },
        )

    respx.post(f"{api}/jobs").mock(side_effect=search)
    respx.get(f"{api}/job/Pune/Data-Analyst_R1").mock(
        return_value=httpx.Response(
            200,
            json={
                "jobPostingInfo": {
                    "title": "Data Analyst",
                    "jobDescription": "<p>SQL and Python. Visa sponsorship is not available.</p>",
                    "location": "Pune, India",
                    "startDate": "2026-09-01",
                    "timeType": "Full time",
                    "jobReqId": "R1",
                    "externalUrl": "https://examplecorp.wd5.myworkdayjobs.com/Careers/job/Pune/Data-Analyst_R1",
                }
            },
        )
    )
    config, identity = validate_config(
        SourceType.WORKDAY,
        {"url": "https://examplecorp.wd5.myworkdayjobs.com/en-US/Careers", "countries": ["India"]},
        _settings(),
    )
    assert identity == "workday:examplecorp:careers"
    jobs = await build_adapter(SourceType.WORKDAY, config, http).discover_jobs()
    assert [(j.external_id, j.title, j.location) for j in jobs] == [
        ("R1", "Data Analyst", "Pune, India")
    ]
    assert searches[-1]["appliedFacets"] == {"locationCountry": ["in-id"]}
    assert "India" in normalize(jobs[0]).countries

    # Hourly re-runs skip postings the source already returned (no detail request).
    adapter = build_adapter(SourceType.WORKDAY, config, http)
    adapter.known = KnownPostings(urls=frozenset({jobs[0].url or ""}))  # type: ignore[attr-defined]
    detail_calls = respx.calls.call_count
    assert await adapter.discover_jobs() == []
    assert all("/job/" not in str(c.request.url) for c in respx.calls[detail_calls:])


def test_workday_rejects_non_workday_urls() -> None:
    from careeros.core.errors import ValidationFailedError

    with pytest.raises(ValidationFailedError):
        validate_config(
            SourceType.WORKDAY, {"url": "https://evil.example.com/Careers"}, _settings()
        )


@respx.mock
async def test_amazon_adapter_reads_search_json(http: PoliteHttpClient) -> None:
    respx.get("https://www.amazon.jobs/robots.txt").mock(
        return_value=httpx.Response(200, text="User-agent: *\nDisallow: /internal\n")
    )
    job = {
        "id_icims": "3088775",
        "title": "Software Development Engineer I",
        "job_path": "/en/jobs/3088775/sde-1",
        "location": "IN, KA, Bengaluru",
        "normalized_location": "Bengaluru, Karnataka, IND",
        "posted_date": "October  1, 2026",
        "description": "<p>Build services.</p>",
        "basic_qualifications": "- Java or Python",
        "is_intern": False,
        "job_schedule_type": "full-time",
        "university_job": True,
    }
    route = respx.get("https://www.amazon.jobs/en/search.json").mock(
        return_value=httpx.Response(200, json={"hits": 1, "jobs": [job]})
    )
    config, identity = validate_config(SourceType.AMAZON, {"countries": ["India"]}, _settings())
    assert identity == "amazon:india"
    [raw] = await build_adapter(SourceType.AMAZON, config, http).discover_jobs()
    assert raw.url == "https://www.amazon.jobs/en/jobs/3088775/sde-1"
    assert "Basic qualifications" in (raw.description_html or "")
    norm = normalize(raw)
    assert norm.countries == ["India"]
    params = route.calls[0].request.url.params
    assert params["normalized_country_code[]"] == "IND"
    assert "software-development" in params.get_list("category[]")


@respx.mock
async def test_oracle_cloud_adapter_uses_location_facet(http: PoliteHttpClient) -> None:
    api = "https://jpmc.fa.oraclecloud.com/hcmRestApi/resources/latest"
    searches: list[str] = []

    def search(request: httpx.Request) -> httpx.Response:
        finder = request.url.params["finder"]
        searches.append(finder)
        if "facetsList=LOCATIONS" in finder:
            facets = [{"Id": 42, "Name": "India", "TotalCount": 1}]
            return httpx.Response(200, json={"items": [{"locationsFacet": facets}]})
        row = {
            "Id": "210001",
            "Title": "Software Engineer I",
            "PrimaryLocation": "Mumbai, Maharashtra, India",
            "PrimaryLocationCountry": "IN",
            "PostedDate": "2026-10-01",
            "ShortDescriptionStr": "Short.",
        }
        return httpx.Response(
            200, json={"items": [{"TotalJobsCount": 1, "requisitionList": [row]}]}
        )

    respx.get(f"{api}/recruitingCEJobRequisitions").mock(side_effect=search)
    respx.get(f"{api}/recruitingCEJobRequisitionDetails").mock(
        return_value=httpx.Response(
            200, json={"items": [{"ExternalDescriptionStr": "<p>Full description.</p>"}]}
        )
    )
    config, identity = validate_config(
        SourceType.ORACLE_CLOUD,
        {
            "host": "https://jpmc.fa.oraclecloud.com",
            "site_number": "CX_1001",
            "company_name": "JPMorgan Chase",
            "countries": ["India"],
        },
        _settings(),
    )
    assert identity == "oracle:jpmc.fa.oraclecloud.com:cx_1001"
    adapter = build_adapter(SourceType.ORACLE_CLOUD, config, http)
    [raw] = await adapter.discover_jobs()
    assert raw.description_html == "<p>Full description.</p>"
    assert (raw.url or "").endswith("/sites/CX_1001/job/210001")
    assert any("selectedLocationsFacet=42" in f for f in searches)

    adapter.known = KnownPostings(ids=frozenset({"210001"}))  # type: ignore[attr-defined]
    assert await adapter.discover_jobs() == []


@respx.mock
async def test_greenhouse_large_board_falls_back_to_light_listing(
    http: PoliteHttpClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from careeros.discovery.adapters import greenhouse

    monkeypatch.setattr(greenhouse, "BOARD_API_MAX_BYTES", 3000)
    api = "https://boards-api.greenhouse.io/v1/boards/bigco/jobs"
    sydney = {"id": 1, "title": "Graduate Engineer", "location": {"name": "Sydney, Australia"}}
    texas = {"id": 2, "title": "Engineer", "location": {"name": "Austin, Texas"}}
    known = {"id": 3, "title": "Intern", "location": {"name": "Melbourne, Australia"}}
    padded = [{**job, "content": "x" * 2000} for job in (sydney, texas, known)]
    respx.get(api, params={"content": "true"}).mock(
        return_value=httpx.Response(200, json={"jobs": padded})
    )
    respx.get(api).mock(return_value=httpx.Response(200, json={"jobs": [sydney, texas, known]}))
    detail = respx.get(f"{api}/1").mock(
        return_value=httpx.Response(200, json={**sydney, "content": "<p>Build things.</p>"})
    )
    adapter = build_adapter(
        SourceType.GREENHOUSE,
        {"board_token": "bigco", "company_name": "BigCo", "countries": ["Australia"]},
        http,
    )
    adapter.known = KnownPostings(ids=frozenset({"3"}))  # type: ignore[attr-defined]
    jobs = await adapter.discover_jobs()
    assert [(j.external_id, j.description_html) for j in jobs] == [
        ("1", "<p>Build things.</p>"),
        ("3", None),  # known: still listed, no detail request
    ]
    assert detail.call_count == 1
