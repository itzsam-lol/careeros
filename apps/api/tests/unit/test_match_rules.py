"""Matching rules that keep the ranking honest for one person's profile (scorer v2)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import pytest

from careeros.core.enums import RemotePreference, RemoteType, SeniorityLevel
from careeros.intelligence.domains import JobDomain
from careeros.intelligence.extraction import JobExtraction
from careeros.intelligence.functions import JobFunction, title_functions
from careeros.intelligence.skills import canonical_key, lookup
from careeros.jobs.models import Job
from careeros.matching.coverage import IMPLIED_BY, CoverageStatus, assess
from careeros.matching.eligibility import CheckStatus, evaluate_eligibility
from careeros.matching.profile_view import MatchProfile, SkillEvidence
from careeros.matching.scoring import compute_scores, function_fit, level_fit, role_alignment
from careeros.profile.enums import SponsorshipRequirement

TARGETS = ["Software Engineer", "Machine Learning Engineer", "Data Analyst", "Research Intern"]


def _profile(**overrides: Any) -> MatchProfile:
    skills = {
        canonical_key(name): SkillEvidence(name, 1.0, ["skills", f"project:{project}"], True)
        for name, project in [
            ("Python", "SecondAsk"),
            ("FastAPI", "SecondAsk"),
            ("TypeScript", "CodeForge"),
            ("PostgreSQL", "CodeForge"),
            ("scikit-learn", "PGIP"),
        ]
    }
    values: dict[str, Any] = {
        "profile_id": uuid.uuid4(),
        "version": 1,
        "skills": skills,
        "highest_degree": None,
        "pursuing_degree": None,
        "is_student": True,
        "expected_graduation_year": 2027,
        "professional_years": 0.2,
        "internship_months": 6.0,
        "authorized_countries": {"India"},
        "sponsorship_requirement": SponsorshipRequirement.REQUIRED,
        "target_roles": TARGETS,
        "target_domains": {JobDomain.ML_AI, JobDomain.BACKEND, JobDomain.DATA},
        "target_countries": {"India", "Australia"},
        "target_cities": set(),
        "target_companies": set(),
        "excluded_companies": set(),
        "excluded_keywords": [],
        "employment_types": set(),
        "remote_preference": RemotePreference.ANY,
        "include_research": True,
        "min_compensation": None,
        "compensation_currency": None,
        "has_research": False,
        "has_publications": False,
        "target_functions": {f for role in TARGETS for f in title_functions(role)},
    }
    values.update(overrides)
    return MatchProfile(**values)


def _job(title: str, **overrides: Any) -> Job:
    values: dict[str, Any] = {
        "title": title,
        "company": "Acme",
        "location": "Bengaluru, India",
        "locations": ["Bengaluru, India"],
        "countries": ["India"],
        "remote_type": RemoteType.ONSITE,
        "seniority": SeniorityLevel.UNKNOWN,
        "employment_type": None,
        "is_active": True,
        "deadline": None,
        "salary_max": None,
        "currency": None,
    }
    values.update(overrides)
    return Job(**values)


def _extraction(title: str, **overrides: Any) -> JobExtraction:
    return JobExtraction(role_title=title, company="Acme", **overrides)


@pytest.mark.parametrize(
    ("title", "functions"),
    [
        ("Software Engineer", {JobFunction.ENGINEERING}),
        ("Machine Learning Engineer", {JobFunction.DATA, JobFunction.ENGINEERING}),
        ("Product Analyst", {JobFunction.DATA}),
        ("Strategic Account Executive - Turkey", {JobFunction.SALES}),
        ("Sales Engineer", {JobFunction.SALES}),
        ("Customer Success Manager", {JobFunction.CUSTOMER}),
        ("Technical Support Engineer", {JobFunction.CUSTOMER}),
        ("Marketing Data Analyst", {JobFunction.DATA}),
        ("Growth Marketing Analyst", {JobFunction.MARKETING}),
        ("Financial Analyst", {JobFunction.FINANCE}),
        ("Associate - F&A - AP 5A", {JobFunction.FINANCE}),
        ("Specialist - F&A - R2R 4A", {JobFunction.FINANCE}),
        ("Specialist - S&P - Sourcing 4B", {JobFunction.OPERATIONS}),
        ("AR/VR Engineer", {JobFunction.ENGINEERING}),
        ("Operations Research Analyst", {JobFunction.RESEARCH}),
        ("Software Engineer, Finance Systems", {JobFunction.ENGINEERING}),
        (
            "Binance Accelerator Program - AI Engineer, Dev Tools",
            {JobFunction.ENGINEERING, JobFunction.DATA},
        ),
        ("AI/ML Engineer", {JobFunction.ENGINEERING, JobFunction.DATA}),
        ("Senior Product Manager, Payments", {JobFunction.PRODUCT}),
        ("Recruiter", {JobFunction.PEOPLE}),
        ("Graduate Trainee", set()),
        ("ENGINEER, SIG ELECTRICAL DESIGN", {JobFunction.HARDWARE}),
        ("Memory Circuit Design Engineer", {JobFunction.HARDWARE}),
        ("Electronics Software Engineer", {JobFunction.ENGINEERING}),
        ("Product Engineer", {JobFunction.ENGINEERING}),
        ("Solutions Consultant", {JobFunction.SALES}),
        ("Affiliate BD - Greater China", {JobFunction.SALES}),
        (
            "Analyst, Algorithm Research & Development",
            {JobFunction.ENGINEERING, JobFunction.RESEARCH},
        ),
    ],
)
def test_title_functions(title: str, functions: set[JobFunction]) -> None:
    assert title_functions(title) == functions


def test_implied_skills_name_real_taxonomy_entries() -> None:
    for skill, sources in IMPLIED_BY.items():
        assert lookup(skill) is not None, skill
        for source in sources:
            assert lookup(source) is not None, (skill, source)


def test_framework_experience_implies_rest_apis_as_partial() -> None:
    coverage = assess("REST APIs", True, _profile())
    assert coverage.status == CoverageStatus.PARTIAL
    assert coverage.note == "shown through FastAPI"
    assert coverage.score == pytest.approx(0.75)
    assert "project:SecondAsk" in coverage.sources
    assert assess("Kubernetes", True, _profile()).status == CoverageStatus.MISSING


def test_role_type_mismatch_is_not_rescued_by_the_company_domain() -> None:
    mp = _profile()
    ai_domain = _extraction("Strategic Account Executive", domain=JobDomain.ML_AI)
    assert function_fit("Strategic Account Executive", mp) is False
    assert role_alignment("Strategic Account Executive", ai_domain, mp) == 0.0
    assert function_fit("Backend Engineer", mp) is True
    assert role_alignment("Backend Engineer", ai_domain, mp) >= 0.85
    assert function_fit("Graduate Trainee", mp) is None  # unclear titles are not penalised


def test_level_fit_prefers_entry_roles_for_students() -> None:
    student = _profile()
    assert level_fit(SeniorityLevel.ENTRY, student) == 1.0
    assert level_fit(SeniorityLevel.INTERN, student) == 1.0
    assert level_fit(SeniorityLevel.MID, student) < 0.5
    assert level_fit(SeniorityLevel.SENIOR, student) < level_fit(SeniorityLevel.MID, student)
    graduate = _profile(is_student=False)
    assert level_fit(SeniorityLevel.INTERN, graduate) < level_fit(SeniorityLevel.ENTRY, graduate)
    experienced = _profile(is_student=False, professional_years=7)
    assert level_fit(SeniorityLevel.SENIOR, experienced) > level_fit(
        SeniorityLevel.ENTRY, experienced
    )


def test_remote_roles_restricted_to_other_countries_fail_location() -> None:
    mp = _profile()
    now = datetime(2026, 9, 30, tzinfo=UTC)
    turkey = _job("Software Engineer", location="Remote, Turkey", locations=["Remote, Turkey"],
                  countries=["Turkey"], remote_type=RemoteType.REMOTE)  # fmt: skip
    checks = {
        c.key: c
        for c in evaluate_eligibility(turkey, _extraction("Software Engineer"), mp, now=now)
    }
    assert checks["location"].status == CheckStatus.FAIL
    assert "Turkey" in checks["location"].detail

    anywhere = _job("Software Engineer", location="Remote", locations=["Remote"], countries=[],
                    remote_type=RemoteType.REMOTE)  # fmt: skip
    checks = {
        c.key: c
        for c in evaluate_eligibility(anywhere, _extraction("Software Engineer"), mp, now=now)
    }
    assert checks["location"].status == CheckStatus.PASS


def test_entry_engineering_role_outranks_sales_role_at_an_ai_company() -> None:
    mp = _profile()
    now = datetime(2026, 9, 30, tzinfo=UTC)

    def score(job: Job, extraction: JobExtraction) -> tuple[float, list[str]]:
        checks = evaluate_eligibility(job, extraction, mp, now=now)
        coverage = [assess(s, True, mp) for s in extraction.required_skills]
        scores = compute_scores(job=job, extraction=extraction, mp=mp, coverage=coverage, hits=[],
                                checks=checks, eligible=True)  # fmt: skip
        return scores.overall, scores.notes

    sde = _job("SDE I")
    sde_x = _extraction("SDE I", domain=JobDomain.BACKEND,
                        required_skills=["Python", "REST APIs", "PostgreSQL", "Kubernetes"])  # fmt: skip
    sales = _job("Strategic Account Executive")
    sales_x = _extraction("Strategic Account Executive", domain=JobDomain.ML_AI,
                          required_skills=["Python"])  # fmt: skip
    mid = _job("Software Engineer II", seniority=SeniorityLevel.MID)
    mid_x = sde_x.model_copy(update={"role_title": "Software Engineer II"})

    sde_score, sde_notes = score(sde, sde_x)
    sales_score, sales_notes = score(sales, sales_x)
    mid_score, mid_notes = score(mid, mid_x)
    assert sde_score > mid_score > sales_score
    assert sales_score < 0.4
    assert any("sales" in note for note in sales_notes)
    assert any("Mid-level" in note for note in mid_notes)
    assert sde_notes == []
