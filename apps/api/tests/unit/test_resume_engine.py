from __future__ import annotations

from pathlib import Path

import pytest

from careeros.resumes.document import parse
from careeros.resumes.latex import compile_tex, escape, find_engine, make_portable
from careeros.resumes.tailor import (
    JobTarget,
    LibraryProject,
    Scorer,
    TailorOptions,
    tailor,
    trim_one,
    validate_rewrite,
)

SAMPLE = Path(__file__).resolve().parents[4] / "fixtures" / "resumes" / "sample_resume.tex"

BACKEND = JobTarget(
    title="Backend Engineer",
    company="Acme Payments",
    required_skills=["Python", "PostgreSQL", "Docker"],
    preferred_skills=["Kubernetes", "Redis"],
    keywords=["payments", "APIs"],
    responsibilities=["Build payment APIs and background workers"],
)

LIBRARY = [
    LibraryProject(
        "Queue Keeper: Job Scheduler",
        ["Python", "Redis"],
        [
            "Built a Redis-backed job scheduler in Python with retries and dead-letter queues.",
            "Drew a logo for the project website.",
        ],
        "https://example.com/queue",
    ),
    LibraryProject("Sketchpad: Drawing App", ["Swift"], ["Built an iPad drawing app with layers."]),
]


@pytest.fixture
def master() -> str:
    return SAMPLE.read_text(encoding="utf-8")


def test_parse_round_trips_exactly(master: str) -> None:
    doc = parse(master)
    assert doc.render() == master
    for section in doc.sections:
        section.changed = True  # force every section through its structured renderer
    assert doc.render() == master
    roles = {s.role: s.kind for s in doc.sections}
    assert roles == {
        "summary": "summary",
        "education": "entries",
        "experience": "entries",
        "projects": "entries",
        "leadership": "list",
        "skills": "skills",
    }


def test_tailor_reorders_swaps_and_adds_only_verified_skills(master: str) -> None:
    doc, result = tailor(
        master, BACKEND, library=LIBRARY, verified_skills=["Docker", "Redis", "Swift"]
    )
    tex = doc.render()
    # The most relevant experience bullet moves to the top.
    experience = doc.section("experience")
    assert experience is not None
    assert experience.entries[0].items is not None
    assert "FastAPI service backed by PostgreSQL" in experience.entries[0].items.bullets[0].tex
    # A verified library project that matches the job replaces a weaker one.
    assert "Queue Keeper" in tex
    assert "Sketchpad" not in tex
    # Verified skills the job asks for are added to a skills line; others are not.
    skills = doc.section("skills")
    assert skills is not None
    assert any("Docker" in line.items for line in skills.skills)
    assert "Redis" in tex
    assert "Swift" not in tex
    # Kubernetes is wanted but not verified: it must never appear.
    assert "Kubernetes" not in tex
    assert result.coverage_after > result.coverage_before
    kinds = {c.kind for c in result.changes}
    assert {"reorder", "swap_in", "add_skill"} <= kinds
    # Untouched sections are byte-identical to the master.
    assert "\\section{Summary}\nFinal-year computer science student" in tex
    assert "\\begin{center}\n{\\LARGE\\bfseries ALEX RIVERA}" in tex


def test_tailor_is_a_no_op_for_an_unrelated_job(master: str) -> None:
    unrelated = JobTarget(title="Pastry Chef", company="Bakery", required_skills=["Baking"])
    doc, result = tailor(
        master, unrelated, options=TailorOptions(swap_projects=False, add_skills=False)
    )
    assert doc.render().count("\\item") == master.count("\\item")
    assert "add_skill" not in {c.kind for c in result.changes}


def test_trim_prefers_projects_and_activities_over_experience(master: str) -> None:
    doc, _ = tailor(master, BACKEND, library=LIBRARY)
    experience = doc.section("experience")
    assert experience is not None
    assert experience.entries[0].items is not None
    before = len(experience.entries[0].items.bullets)
    change = trim_one(doc, Scorer(BACKEND))
    assert change is not None
    assert len(experience.entries[0].items.bullets) == before  # experience is protected first
    assert parse(doc.render()).render() == doc.render()  # still a valid, parseable document


@pytest.mark.parametrize(
    ("original", "rewrite", "problem"),
    [
        (
            "Built a FastAPI service that served 20,000 requests a day.",
            "Engineered a FastAPI service handling 20,000 daily requests.",
            None,
        ),
        (
            "Built a FastAPI service that served 20,000 requests a day.",
            "Built a FastAPI service that served 50,000 requests a day.",
            "introduced numbers",
        ),
        (
            "Built a FastAPI service that served 20,000 requests a day.",
            "Built a FastAPI and Kubernetes service that served 20,000 requests a day.",
            "introduced skills",
        ),
        (
            "Built a FastAPI service that served 20,000 requests a day.",
            "Built a FastAPI service at Google that served 20,000 requests a day.",
            "introduced names",
        ),
        ("Built a FastAPI service that served 20,000 requests a day.", "Built it.", "length"),
    ],
)
def test_rewrite_validator(original: str, rewrite: str, problem: str | None) -> None:
    result = validate_rewrite(original, rewrite, allowed_skills=set())
    if problem is None:
        assert result is None
    else:
        assert result is not None
        assert problem in result


def test_latex_helpers() -> None:
    assert escape("50% of $10 & more_") == r"50\% of \$10 \& more\_"
    assert escape("Dean\u2019s \u2013 list") == "Dean's -- list"
    portable = make_portable("\\input{glyphtounicode}\n\\pdfgentounicode=1\nx")
    assert portable.startswith("\\ifdefined\\pdfgentounicode")


@pytest.mark.latex
@pytest.mark.skipif(find_engine() is None, reason="no LaTeX engine installed")
async def test_tailored_resume_compiles_to_one_page(master: str) -> None:
    doc, _ = tailor(master, BACKEND, library=LIBRARY, verified_skills=["Docker", "Redis"])
    result = await compile_tex(doc.render())
    assert result.pages == 1
    assert result.pdf.startswith(b"%PDF")
