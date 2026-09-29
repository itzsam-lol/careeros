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
