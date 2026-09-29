from __future__ import annotations

import pytest

from careeros.intelligence.skills import (
    SkillCategory,
    canonical_key,
    extract_skill_names,
    normalize_skill_name,
    skill_category,
)


def test_aliases_resolve_to_canonical_names() -> None:
    text = "Python, C/C++ (C++17), Go and R. Knowledge of k8s, sklearn, PyTorch and Node.js."
    assert extract_skill_names(text) == [
        "Python",
        "C",
        "C++",
        "Go",
        "R",
        "Kubernetes",
        "scikit-learn",
        "PyTorch",
        "Node.js",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "You will go above and beyond for customers. Go to our careers page.",
        "Join our R&D team after our Series C funding.",
        "You will collaborate with the rest of the team.",
        "Spring 2027 internship cohort.",
        "Run services locally with docker compose.",
        "Meet us at the Career Expo next week.",
        "Experience with HCL is not a skill; neither is vertex cover.",
        "We react quickly and excel under pressure.",
    ],
)
def test_ambiguous_english_words_are_not_skills(text: str) -> None:
    names = set(extract_skill_names(text))
    assert not names & {
        "Go", "R", "C", "REST APIs", "Spring", "Jetpack Compose", "Expo",
        "Terraform", "Vertex AI", "React", "Excel",
    }  # fmt: skip


def test_qualified_forms_of_ambiguous_skills_match() -> None:
    text = (
        "Spring Boot and Spring Framework, REST APIs, Excel, React Native and React, "
        "Expo Router, golang, AI/ML with LLMs and RAG."
    )
    names = extract_skill_names(text)
    for expected in (
        "Spring Boot", "Spring", "REST APIs", "Excel", "React Native", "React", "Expo", "Go",
        "Artificial Intelligence", "Machine Learning", "Large Language Models",
        "Retrieval-Augmented Generation",
    ):  # fmt: skip
        assert expected in names, expected


def test_symbol_heavy_names() -> None:
    names = extract_skill_names("C#, F#, .NET, ASP.NET, Objective-C and Next.js")
    assert names == ["C#", "F#", ".NET", "Objective-C", "Next.js"]


def test_normalisation_helpers() -> None:
    assert canonical_key("Node.js") == "nodejs"
    assert normalize_skill_name("k8s") == "Kubernetes"
    assert normalize_skill_name("  Some   Niche Tool ") == "Some Niche Tool"
    assert skill_category("pytorch") == SkillCategory.ML_AI
    assert skill_category("unknown thing") == SkillCategory.OTHER
