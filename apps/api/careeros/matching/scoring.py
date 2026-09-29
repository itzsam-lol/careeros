"""Semantic dimensions and the overall relevance score (explicitly not a hiring probability)."""

from __future__ import annotations

from dataclasses import dataclass

from careeros.core.enums import RemotePreference, RemoteType
from careeros.discovery.normalize import normalize_title
from careeros.evidence.service import EvidenceHit
from careeros.intelligence.extraction import JobExtraction
from careeros.jobs.models import Job
from careeros.matching.coverage import RequirementCoverage, skills_score
from careeros.matching.eligibility import CheckStatus, EligibilityCheck
from careeros.matching.profile_view import MatchProfile
from careeros.profile.enums import VerificationStatus

SCORER_VERSION = "match-v1"
DEFAULT_WEIGHTS = {
    "skills": 0.3, "projects": 0.2, "experience": 0.15, "research": 0.05, "domain": 0.15, "preferences": 0.15,
}  # fmt: skip
RESEARCH_WEIGHTS = {
    "skills": 0.25, "projects": 0.15, "experience": 0.1, "research": 0.25, "domain": 0.1, "preferences": 0.15,
}  # fmt: skip
_TITLE_NOISE = {"intern", "internship", "senior", "junior", "lead", "staff", "principal", "i", "ii", "iii", "the", "and", "of"}  # fmt: skip
UNVERIFIED_DISCOUNT = 0.6


@dataclass(frozen=True, slots=True)
class Scores:
    dimensions: dict[str, float]
    overall: float
    weights: dict[str, float]


def hit_relevance(hit: EvidenceHit) -> float:
    discount = (
        1.0 if hit.item.verification_status == VerificationStatus.VERIFIED else UNVERIFIED_DISCOUNT
    )
    return hit.relevance * discount


def _blend(values: list[float]) -> float:
    ordered = sorted(values, reverse=True)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return ordered[0]
    return 0.7 * ordered[0] + 0.3 * ordered[1]


def _by_type(hits: list[EvidenceHit], *types: str) -> list[float]:
    return [hit_relevance(h) for h in hits if h.item.source_type in types]


def role_alignment(title: str, extraction: JobExtraction, mp: MatchProfile) -> float:
    title_tokens = set(normalize_title(title).split()) - _TITLE_NOISE
    best = 0.0
    for target in mp.target_roles:
        target_tokens = set(normalize_title(target).split()) - _TITLE_NOISE
        if title_tokens and target_tokens:
            best = max(best, len(title_tokens & target_tokens) / len(title_tokens | target_tokens))
    domain_hit = extraction.domain in mp.target_domains
    return min(1.0, max(best * 1.4, 0.8 if domain_hit else 0.0))


def preference_score(
    job: Job, extraction: JobExtraction, mp: MatchProfile, checks: list[EligibilityCheck]
) -> float:
    signals: list[float] = []
    if mp.target_roles:
        signals.append(role_alignment(job.title, extraction, mp))
    by_key = {check.key: check for check in checks}
    for key in ("location", "employment_type"):
        if key in by_key:
            signals.append(
                {CheckStatus.PASS: 1.0, CheckStatus.UNKNOWN: 0.5, CheckStatus.FAIL: 0.0}[
                    by_key[key].status
                ]
            )
    if mp.remote_preference != RemotePreference.ANY and job.remote_type != RemoteType.UNKNOWN:
        compatible = {
            RemotePreference.REMOTE: {RemoteType.REMOTE},
            RemotePreference.HYBRID: {RemoteType.HYBRID, RemoteType.REMOTE},
            RemotePreference.ONSITE: {RemoteType.ONSITE, RemoteType.HYBRID},
        }[mp.remote_preference]
        signals.append(1.0 if job.remote_type in compatible else 0.3)
    if job.company.strip().lower() in mp.target_companies:
        signals.append(1.0)
    if (
        mp.min_compensation
        and job.salary_max
        and job.currency
        and mp.compensation_currency
        and job.currency.upper() == mp.compensation_currency.upper()
    ):
        signals.append(1.0 if job.salary_max >= mp.min_compensation else 0.2)
    if extraction.is_research and not mp.include_research:
        signals.append(0.3)
    return sum(signals) / len(signals) if signals else 0.6


def compute_scores(
    *,
    job: Job,
    extraction: JobExtraction,
    mp: MatchProfile,
    coverage: list[RequirementCoverage],
    hits: list[EvidenceHit],
    checks: list[EligibilityCheck],
    eligible: bool,
) -> Scores:
    skills = skills_score(coverage)
    if skills is None:
        skills = _blend(_by_type(hits, "skills")) or 0.5
    projects = _blend(_by_type(hits, "project"))
    experience = _blend(_by_type(hits, "experience"))
    if any(c.key == "experience" and c.status == CheckStatus.PASS for c in checks):
        experience = min(1.0, experience + 0.1)
    research = max(_by_type(hits, "research", "publication") or [0.0])
    if extraction.is_research and mp.has_publications:
        research = min(1.0, research + 0.1)
    overall_relevance = max((hit_relevance(h) for h in hits), default=0.0)
    if mp.target_domains:
        domain_fit = 1.0 if extraction.domain in mp.target_domains else 0.3
    else:
        domain_fit = 0.6
    domain = 0.5 * domain_fit + 0.5 * overall_relevance
    preferences = preference_score(job, extraction, mp, checks)

    dimensions = {
        "skills": round(skills, 3),
        "projects": round(projects, 3),
        "experience": round(experience, 3),
        "research": round(research, 3),
        "domain": round(domain, 3),
        "preferences": round(preferences, 3),
    }
    weights = RESEARCH_WEIGHTS if extraction.is_research else DEFAULT_WEIGHTS
    overall = sum(weights[k] * v for k, v in dimensions.items())
    if not eligible:
        overall = min(overall * 0.5, 0.45)
    elif any(c.status == CheckStatus.UNKNOWN and c.key == "work_authorization" for c in checks):
        overall *= 0.9
    return Scores(
        dimensions=dimensions, overall=round(max(0.0, min(1.0, overall)), 3), weights=weights
    )
