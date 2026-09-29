from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from careeros.core.enums import CompensationPeriod
from careeros.discovery.normalize import normalize
from careeros.discovery.raw import RawJob
from careeros.intelligence.domains import JobDomain
from careeros.intelligence.extraction import (
    DegreeLevel,
    JobExtraction,
    LLMExtraction,
    Sponsorship,
    heuristic_extract,
    merge_llm,
    parse_deadline,
    parse_salary,
    split_sections,
)

FEED = Path(__file__).resolve().parents[4] / "fixtures" / "jobs" / "demo_feed.json"
TODAY = date(2026, 9, 29)


def _job(external_id: str) -> JobExtraction:
    payload: dict[str, Any] = json.loads(FEED.read_text("utf-8"))
    item = next(j for j in payload["jobs"] if j["external_id"] == external_id)
    norm = normalize(RawJob.model_validate(item))
    return heuristic_extract(
        title=norm.title,
        company=norm.company,
        description=norm.description,
        locations=norm.locations,
        employment_type=norm.employment_type,
        seniority=norm.seniority,
        remote_type=norm.remote_type,
        application_platform=norm.application_platform.value,
        today=TODAY,
    )


def test_ml_intern_extraction() -> None:
    ex = _job("nimbus-ml-intern")
    for skill in ("Python", "PyTorch", "FastAPI", "Docker", "Google Cloud", "Hugging Face"):
        assert skill in ex.required_skills, skill
    assert "LangChain" in ex.preferred_skills
    assert "pgvector" in ex.preferred_skills
    assert not set(ex.required_skills) & set(ex.preferred_skills)
    assert ex.requires_current_student is True
    assert ex.graduation_years == [2027]
    assert DegreeLevel.BACHELOR in ex.degree_levels
    assert ex.domain == JobDomain.ML_AI
    assert ex.deadline == date(2026, 10, 31)
    assert ex.salary is not None
    assert ex.salary.minimum == 60000
    assert ex.salary.currency == "INR"
    assert ex.salary.period == CompensationPeriod.MONTH
    assert any("Fine-tune transformer models" in r for r in ex.responsibilities)
    assert ex.injection_detected is False


def test_senior_role_requirements() -> None:
    ex = _job("nimbus-senior-mle")
    assert ex.min_years_experience == 6
    assert {DegreeLevel.MASTER, DegreeLevel.PHD} <= set(ex.degree_levels)


def test_sponsorship_denial_and_authorization_country() -> None:
    ex = _job("stellar-ml-intern-us")
    assert ex.sponsorship == Sponsorship.NOT_AVAILABLE
    assert ex.work_authorization_countries == ["United States"]


def test_research_flag() -> None:
    ex = _job("lumen-research-intern")
    assert ex.is_research is True
    assert ex.domain == JobDomain.ML_AI
    assert "Hugging Face" in ex.preferred_skills


def test_prompt_injection_is_ignored_and_flagged() -> None:
    ex = _job("veritas-swe-intern")
    assert ex.injection_detected is True
    assert ex.injection_snippets
    assert "Kubernetes" not in ex.required_skills  # only mentioned inside the injected text
    assert (
        ex.min_years_experience is None
    )  # "10 years of Kubernetes experience" is not a requirement
    assert set(ex.required_skills) >= {"Python", "TypeScript", "Git"}


def test_sections_are_detected() -> None:
    sections = split_sections(
        "Intro text.\nRequirements\n• Python\nNice to have\n• Rust\nBenefits:\n• Snacks"
    )
    assert [kind for kind, _ in sections] == ["intro", "required", "preferred", "other"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Stipend: ₹40,000 per month", (40000, 40000, "INR", CompensationPeriod.MONTH)),
        ("Salary $120k - $150k a year", (120000, 150000, "USD", CompensationPeriod.YEAR)),
        ("CTC Rs 12 LPA", (1_200_000, 1_200_000, "INR", CompensationPeriod.YEAR)),
        ("We pay €25 per hour for contractors", None),  # below the noise floor
    ],
)
def test_salary_parsing(
    text: str, expected: tuple[float, float, str, CompensationPeriod] | None
) -> None:
    salary = parse_salary(text)
    if expected is None:
        assert salary is None
        return
    assert salary is not None
    assert (salary.minimum, salary.maximum, salary.currency, salary.period) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Apply by 31 October 2026.", date(2026, 10, 31)),
        ("Deadline: 15/11/2026", date(2026, 11, 15)),
        ("Applications close on March 3", date(2027, 3, 3)),
        ("No deadline mentioned.", None),
    ],
)
def test_deadline_parsing(text: str, expected: date | None) -> None:
    assert parse_deadline(text, today=TODAY) == expected


def test_llm_output_is_grounded_in_the_posting() -> None:
    base = _job("quasar-backend-intern")
    llm = LLMExtraction(
        required_skills=["Python", "FastAPI", "Rust", "Kubernetes"],  # Rust is not in the posting
        preferred_skills=["Kubernetes"],
        min_years_experience=4,  # the posting never says 4
        sponsorship=Sponsorship.AVAILABLE,
    )
    merged = merge_llm(
        base, llm, "Python FastAPI Django PostgreSQL SQL Docker Git Kubernetes REST APIs"
    )
    assert "Rust" not in merged.required_skills
    assert merged.min_years_experience is None
    assert "Kubernetes" in merged.required_skills
    assert "Kubernetes" not in merged.preferred_skills  # never both required and preferred


def test_explicit_sponsorship_denial_beats_the_model() -> None:
    base = _job("stellar-ml-intern-us")
    llm = LLMExtraction(sponsorship=Sponsorship.AVAILABLE)
    assert merge_llm(base, llm, "unable to sponsor").sponsorship == Sponsorship.NOT_AVAILABLE
