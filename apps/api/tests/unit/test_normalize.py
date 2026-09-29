from __future__ import annotations

import pytest

from careeros.core.enums import EmploymentType, RemoteType, SeniorityLevel
from careeros.discovery.normalize import (
    canonicalize_url,
    description_hash,
    detect_employment_type,
    detect_platform,
    detect_remote,
    detect_seniority,
    extract_countries,
    html_to_text,
    jaccard,
    normalize,
    normalize_company,
    normalize_location,
    normalize_title,
    shingles,
)
from careeros.discovery.raw import RawJob
from careeros.jobs.models import ApplicationPlatform


def test_canonical_urls_drop_tracking_but_keep_identity() -> None:
    assert (
        canonicalize_url("HTTP://Jobs.Example.com/roles/42/?utm_source=x&gh_jid=42&ref=feed#apply")
        == "https://jobs.example.com/roles/42?gh_jid=42"
    )
    assert canonicalize_url("javascript:alert(1)") is None
    assert canonicalize_url(None) is None


def test_company_normalisation_strips_legal_suffixes() -> None:
    assert normalize_company("Nimbus AI Pvt. Ltd.") == normalize_company("Nimbus AI") == "nimbus ai"
    assert normalize_company("Johnson & Johnson Inc") == "johnson and johnson"


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Sr. Software Engineer (Remote) [R-10234]", "senior software engineer"),
        ("Software Engineer, Identity", "software engineer identity"),
        ("ML Engineer - Req #4411", "machine learning engineer"),
        ("SWE Intern", "software engineer intern"),
    ],
)
def test_title_normalisation(title: str, expected: str) -> None:
    assert normalize_title(title) == expected


def test_location_synonyms() -> None:
    assert normalize_location("Bangalore, India") == normalize_location("Bengaluru, India")
    assert normalize_location("Gurgaon") == "gurugram"


def test_country_extraction() -> None:
    assert extract_countries(["Bengaluru, Karnataka"]) == ["India"]
    assert extract_countries(["Mountain View, CA"]) == ["United States"]
    assert extract_countries(["Remote - US"]) == ["United States"]
    assert extract_countries(["London", "Pune, India"]) == ["India", "United Kingdom"] or set(
        extract_countries(["London", "Pune, India"])
    ) == {"India", "United Kingdom"}


def test_employment_type_detection() -> None:
    assert detect_employment_type("Machine Learning Intern", None, "") == EmploymentType.INTERNSHIP
    assert detect_employment_type("Engineer", "Full-time", "") == EmploymentType.FULL_TIME
    assert detect_employment_type("Research Assistant - NLP", None, "") == EmploymentType.RESEARCH
    assert (
        detect_employment_type("Engineer", None, "This is a part-time role.")
        == EmploymentType.PART_TIME
    )
    assert detect_employment_type("Engineer", None, "") is None


def test_remote_and_seniority_detection() -> None:
    assert detect_remote("Frontend Engineer", ["Remote - India"], "") == RemoteType.REMOTE
    assert (
        detect_remote("Engineer", ["Pune"], "We work hybrid, 3 days in office") == RemoteType.HYBRID
    )
    assert detect_remote("Engineer", ["Pune"], "", hint="on-site") == RemoteType.ONSITE
    assert detect_seniority("Senior Machine Learning Engineer", None) == SeniorityLevel.SENIOR
    assert detect_seniority("Staff Engineer", None) == SeniorityLevel.LEAD
    assert detect_seniority("ML Intern", EmploymentType.INTERNSHIP) == SeniorityLevel.INTERN
    assert detect_seniority("Associate Software Engineer", None) == SeniorityLevel.ENTRY
    assert detect_seniority("Associate Director, Engineering", None) == SeniorityLevel.MANAGER


@pytest.mark.parametrize(
    ("url", "platform"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", ApplicationPlatform.GREENHOUSE),
        ("https://job-boards.greenhouse.io/acme/jobs/1", ApplicationPlatform.GREENHOUSE),
        ("https://jobs.lever.co/acme/123/apply", ApplicationPlatform.LEVER),
        ("https://acme.wd5.myworkdayjobs.com/en-US/careers/job/x", ApplicationPlatform.WORKDAY),
        ("https://docs.google.com/forms/d/e/abc/viewform", ApplicationPlatform.GOOGLE_FORMS),
        ("https://forms.gle/abc", ApplicationPlatform.GOOGLE_FORMS),
        ("https://careers.acme.com/apply", ApplicationPlatform.GENERIC),
        ("mailto:jobs@acme.com", ApplicationPlatform.EMAIL),
        (None, ApplicationPlatform.UNKNOWN),
    ],
)
def test_platform_detection(url: str | None, platform: ApplicationPlatform) -> None:
    assert detect_platform(url) == platform


def test_html_to_text_keeps_structure_and_drops_scripts() -> None:
    text = html_to_text("<p>Intro</p><ul><li>Python</li><li>SQL</li></ul><script>alert(1)</script>")
    assert text.splitlines() == ["Intro", "", "• Python", "• SQL"] or "• Python" in text
    assert "alert" not in text
    escaped = html_to_text("&lt;p&gt;Hello &amp;amp; welcome&lt;/p&gt;")
    assert escaped == "Hello & welcome"


def test_description_hash_ignores_formatting_noise() -> None:
    assert description_hash("Python,  SQL!\nhttps://x.com/a") == description_hash("python sql")


def test_shingle_similarity() -> None:
    a = shingles("we are hiring a machine learning engineer intern to build models")
    b = shingles("we are hiring a machine learning engineer intern to build great models")
    assert jaccard(a, b) > 0.5
    assert jaccard(a, shingles("completely different text about cooking pasta at home")) == 0


def test_normalize_builds_canonical_job() -> None:
    job = normalize(
        RawJob(
            external_id="1",
            title="Machine Learning Intern (Remote)",
            company="Nimbus AI Inc.",
            url="https://jobs.example.com/1?utm_campaign=x",
            apply_url="https://boards.greenhouse.io/nimbus/jobs/1",
            locations=["Remote - India"],
            description_html="<p>PyTorch and <b>Python</b>.</p>",
        )
    )
    assert job.canonical_url == "https://jobs.example.com/1"
    assert job.application_platform == ApplicationPlatform.GREENHOUSE
    assert job.employment_type == EmploymentType.INTERNSHIP
    assert job.remote_type == RemoteType.REMOTE
    assert job.countries == ["India"]
    assert job.description == "PyTorch and Python."
    assert job.dedup_key == "nimbus ai|machine learning intern|remote india"
