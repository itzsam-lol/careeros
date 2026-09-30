"""Requirement coverage: which required/preferred skills the verified profile can back up."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any

from careeros.intelligence.extraction import JobExtraction
from careeros.intelligence.skills import canonical_key
from careeros.matching.profile_view import MatchProfile

# Adjacent skills earn partial credit (a PyTorch user can pick up TensorFlow) but never count as
# having the skill: explanations always name the adjacent skill instead.
RELATED_GROUPS: list[set[str]] = [
    {"PyTorch", "TensorFlow", "JAX", "Keras"},
    {"React", "Vue.js", "Angular", "Svelte"},
    {"Next.js", "Nuxt"},
    {"AWS", "Google Cloud", "Microsoft Azure"},
    {"PostgreSQL", "MySQL", "SQL Server", "Oracle Database", "SQLite"},
    {"MongoDB", "DynamoDB", "Cassandra"},
    {"FastAPI", "Flask", "Django"},
    {"Java", "Kotlin", "Scala"},
    {"Tableau", "Power BI", "Looker"},
    {"LangChain", "LlamaIndex"},
    {"Hugging Face", "Transformers"},
    {"pgvector", "Pinecone", "Weaviate", "Milvus", "ChromaDB", "Vector Databases"},
    {"GitHub Actions", "GitLab CI", "Jenkins", "CI/CD"},
    {"Apache Kafka", "Apache Flink", "Apache Spark"},
    {"C", "C++"},
    {"JavaScript", "TypeScript"},
]


# Broad skills that specific, verified tools demonstrate: building FastAPI services is REST API
# work. Credited as PARTIAL with the tool named ("shown through FastAPI"), never as MATCHED.
IMPLIED_BY: dict[str, set[str]] = {
    "REST APIs": {"FastAPI", "Express", "Flask", "Django", "Spring Boot", "NestJS", "API Design"},
    "API Design": {"REST APIs", "GraphQL", "gRPC", "FastAPI", "Express", "Django", "Spring Boot"},
    "Backend Development": {"FastAPI", "Express", "Flask", "Django", "Spring Boot", "NestJS",
                            "Node.js", "Ruby on Rails", ".NET"},
    "Frontend Development": {"React", "Next.js", "Vue.js", "Angular", "Svelte"},
    "Web Development": {"React", "Next.js", "Vue.js", "Angular", "Django", "Express", "FastAPI"},
    "Machine Learning": {"scikit-learn", "TensorFlow", "PyTorch", "XGBoost", "LightGBM", "Keras",
                         "Deep Learning"},
    "Deep Learning": {"TensorFlow", "PyTorch", "Keras", "JAX"},
    "Data Science": {"Machine Learning", "scikit-learn", "Statistics"},
    "Data Analysis": {"Pandas", "SQL", "Statistics"},
    "Data Visualization": {"Matplotlib", "Plotly", "Seaborn", "Tableau", "Power BI", "D3.js"},
    "SQL": {"PostgreSQL", "MySQL", "SQLite", "SQL Server", "Oracle Database", "BigQuery",
            "Snowflake"},
    "Cloud Computing": {"AWS", "Google Cloud", "Microsoft Azure"},
    "Large Language Models": {"LangChain", "LlamaIndex", "Retrieval-Augmented Generation",
                              "Prompt Engineering", "vLLM"},
    "Generative AI": {"Large Language Models", "LangChain", "LlamaIndex",
                      "Retrieval-Augmented Generation", "Prompt Engineering"},
    "Natural Language Processing": {"Large Language Models", "Transformers", "spaCy", "NLTK",
                                    "Hugging Face"},
    "Artificial Intelligence": {"Machine Learning", "Deep Learning", "Large Language Models",
                                "Computer Vision", "Natural Language Processing"},
    "Computer Vision": {"OpenCV"},
    "Object-Oriented Programming": {"Java", "C++", "C#", "Kotlin", "Scala"},
    "Unit Testing": {"pytest", "Jest", "JUnit", "Cypress"},
}  # fmt: skip
IMPLIED_SCORE = 0.75


class CoverageStatus(StrEnum):
    MATCHED = "MATCHED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"


@dataclass
class RequirementCoverage:
    skill: str
    required: bool
    status: CoverageStatus
    score: float
    sources: list[str] = field(default_factory=list)
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": self.status.value}


def _related(skill: str) -> set[str]:
    for group in RELATED_GROUPS:
        if skill in group:
            return group - {skill}
    return set()


def assess(skill: str, required: bool, mp: MatchProfile) -> RequirementCoverage:
    evidence = mp.skill(skill)
    if evidence is not None and evidence.weight >= 0.75:
        return RequirementCoverage(
            skill, required, CoverageStatus.MATCHED, min(1.0, evidence.weight), evidence.sources
        )
    if evidence is not None and evidence.weight > 0:
        note = (
            "in your profile but not verified yet"
            if not evidence.verified
            else "only indirectly evidenced"
        )
        return RequirementCoverage(
            skill, required, CoverageStatus.PARTIAL, evidence.weight * 0.8, evidence.sources, note
        )
    implied = [
        found
        for name in sorted(IMPLIED_BY.get(skill, ()))
        if (found := mp.skills.get(canonical_key(name))) is not None and found.weight >= 0.75
    ]
    if implied:
        names = ", ".join(e.name for e in implied[:2])
        sources = list(dict.fromkeys(s for e in implied for s in e.sources))[:6]
        return RequirementCoverage(
            skill,
            required,
            CoverageStatus.PARTIAL,
            IMPLIED_SCORE,
            sources,
            f"shown through {names}",
        )
    for other in sorted(_related(skill)):
        adjacent = mp.skills.get(canonical_key(other))
        if adjacent is not None and adjacent.weight >= 0.75:
            return RequirementCoverage(
                skill,
                required,
                CoverageStatus.PARTIAL,
                0.4,
                adjacent.sources,
                f"related experience: {adjacent.name}",
            )
    return RequirementCoverage(skill, required, CoverageStatus.MISSING, 0.0)  # fmt: skip


def requirement_coverage(extraction: JobExtraction, mp: MatchProfile) -> list[RequirementCoverage]:
    required = [assess(skill, True, mp) for skill in extraction.required_skills]
    preferred = [assess(skill, False, mp) for skill in extraction.preferred_skills]
    return [*required, *preferred]


SHRINKAGE_WEIGHT = 2.0  # pseudo-requirements pulling short lists toward a neutral prior
NEUTRAL_PRIOR = 0.5


def skills_score(coverage: list[RequirementCoverage]) -> float | None:
    """Weighted coverage (required skills count double), shrunk toward a neutral prior.

    Covering all 3 skills of a vague posting is weaker evidence of fit than covering 10 of 12
    in a detailed one, so short requirement lists are pulled toward 0.5. None when the JD lists
    no skills at all.
    """
    if not coverage:
        return None
    total = sum(1.0 if c.required else 0.5 for c in coverage)
    earned = sum((1.0 if c.required else 0.5) * c.score for c in coverage)
    return (earned + NEUTRAL_PRIOR * SHRINKAGE_WEIGHT) / (total + SHRINKAGE_WEIGHT)
