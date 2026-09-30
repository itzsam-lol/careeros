"""Semantic dimensions and the overall relevance score (explicitly not a hiring probability)."""

from __future__ import annotations

from dataclasses import dataclass, field

from careeros.core.enums import RemotePreference, RemoteType, SeniorityLevel
from careeros.discovery.normalize import detect_seniority, normalize_title
from careeros.evidence.service import EvidenceHit
from careeros.intelligence.extraction import JobExtraction
from careeros.intelligence.functions import LABELS, title_functions
from careeros.jobs.models import Job
from careeros.matching.coverage import CoverageStatus, RequirementCoverage, skills_score
from careeros.matching.eligibility import CheckStatus, EligibilityCheck
from careeros.matching.profile_view import MatchProfile
from careeros.profile.enums import VerificationStatus

# v2: kind of work (title function), role level vs. experience, per-project skill evidence.
# v3: hardware vs. software engineering, specialty after a bare "Engineer," in the title.
SCORER_VERSION = "match-v3"
DEFAULT_WEIGHTS = {
    "skills": 0.3, "projects": 0.2, "experience": 0.15, "research": 0.05, "domain": 0.15, "preferences": 0.15,
}  # fmt: skip
RESEARCH_WEIGHTS = {
    "skills": 0.25, "projects": 0.15, "experience": 0.1, "research": 0.25, "domain": 0.1, "preferences": 0.15,
}  # fmt: skip
_TITLE_NOISE = {"intern", "internship", "senior", "junior", "lead", "staff", "principal", "i", "ii", "iii", "the", "and", "of"}  # fmt: skip
UNVERIFIED_DISCOUNT = 0.6
# Roles in a different line of work (sales, HR, legal...) from every target role sink, even at
# companies in the user's field.
FUNCTION_MISMATCH_FACTOR = 0.6

_S = SeniorityLevel
# How well a role's level suits the user: students and new graduates, <3, <6 and 6+ years.
_LEVEL_FIT: dict[str, dict[SeniorityLevel, float]] = {
    "early": {_S.INTERN: 1.0, _S.ENTRY: 1.0, _S.MID: 0.45, _S.SENIOR: 0.1, _S.LEAD: 0.05, _S.MANAGER: 0.05},
    "junior": {_S.INTERN: 0.4, _S.ENTRY: 0.95, _S.MID: 0.8, _S.SENIOR: 0.35, _S.LEAD: 0.2, _S.MANAGER: 0.2},
    "mid": {_S.INTERN: 0.1, _S.ENTRY: 0.6, _S.MID: 1.0, _S.SENIOR: 0.8, _S.LEAD: 0.5, _S.MANAGER: 0.4},
    "senior": {_S.INTERN: 0.05, _S.ENTRY: 0.3, _S.MID: 0.8, _S.SENIOR: 1.0, _S.LEAD: 0.9, _S.MANAGER: 0.8},
}  # fmt: skip
UNKNOWN_LEVEL_FIT = 0.6


@dataclass(frozen=True, slots=True)
class Scores:
    dimensions: dict[str, float]
    overall: float
    weights: dict[str, float]
    # Caveats for the explanation ("looks like a sales role").
    notes: list[str] = field(default_factory=list)


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


def effective_seniority(job: Job) -> SeniorityLevel:
    """The stored level, or one read from the title (older rows were classified with fewer rules)."""
    if job.seniority != SeniorityLevel.UNKNOWN:
        return job.seniority
    return detect_seniority(job.title, job.employment_type)


def level_fit(level: SeniorityLevel, mp: MatchProfile) -> float:
    if level == SeniorityLevel.UNKNOWN:
        return UNKNOWN_LEVEL_FIT
    years = mp.professional_years
    if mp.is_student or years < 1:
        if level == SeniorityLevel.INTERN and not mp.is_student:
            return 0.6  # internships usually require current enrolment
        return _LEVEL_FIT["early"][level]
    band = "junior" if years < 3 else "mid" if years < 6 else "senior"
    return _LEVEL_FIT[band][level]


def function_fit(title: str, mp: MatchProfile) -> bool | None:
    """Whether the title's kind of work matches a target role; None when either is unknown."""
    if not mp.target_functions:
        return None
    functions = title_functions(title)
    if not functions:
        return None
    return bool(functions & mp.target_functions)


def evidence_skill_fit(coverage: list[RequirementCoverage], prefix: str) -> float:
    """Share of the job's skills that a single project (or job) of the user demonstrates.

    One project that used four of the requested skills is stronger evidence than four
    projects that each used one. Lists shorter than three skills are not a full fit.
    """
    per_item: dict[str, float] = {}
    total = 0.0
    for c in coverage:
        weight = 1.0 if c.required else 0.5
        total += weight
        if c.status != CoverageStatus.MATCHED:
            continue
        for source in c.sources:
            if source.startswith(prefix):
                per_item[source] = per_item.get(source, 0.0) + weight
    if not per_item:
        return 0.0
    return min(1.0, max(per_item.values()) / min(max(total, 3.0), 4.0))


def role_alignment(title: str, extraction: JobExtraction, mp: MatchProfile) -> float:
    title_tokens = set(normalize_title(title).split()) - _TITLE_NOISE
    best = 0.0
    for target in mp.target_roles:
        target_tokens = set(normalize_title(target).split()) - _TITLE_NOISE
        if title_tokens and target_tokens:
            best = max(best, len(title_tokens & target_tokens) / len(title_tokens | target_tokens))
    domain_hit = extraction.domain in mp.target_domains
    fit = function_fit(title, mp)
    if fit is False:
        return 0.0  # a sales role is not an engineering role, whatever the company builds
    if fit:
        return min(1.0, max(best * 1.4, 0.85 if domain_hit else 0.7))
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
    notes: list[str] = []
    skills = skills_score(coverage)
    if skills is None:
        skills = _blend(_by_type(hits, "skills")) or 0.5
    projects = max(_blend(_by_type(hits, "project")), evidence_skill_fit(coverage, "project:"))
    work = max(_blend(_by_type(hits, "experience")), evidence_skill_fit(coverage, "experience:"))
    if any(c.key == "experience" and c.status == CheckStatus.PASS for c in checks):
        work = min(1.0, work + 0.1)
    level = effective_seniority(job)
    fit_for_level = level_fit(level, mp)
    experience = 0.5 * work + 0.5 * fit_for_level
    if level == SeniorityLevel.MID and fit_for_level < 0.6:
        notes.append("Mid-level role: it usually expects a few years of full-time experience")
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
    if function_fit(job.title, mp) is False:
        overall *= FUNCTION_MISMATCH_FACTOR
        kinds = " / ".join(sorted(LABELS[f] for f in title_functions(job.title)))
        notes.insert(
            0, f"This looks like a {kinds} role, not the kind of work in your target roles"
        )
    if not eligible:
        overall = min(overall * 0.5, 0.45)
    elif any(c.status == CheckStatus.UNKNOWN and c.key == "work_authorization" for c in checks):
        overall *= 0.9
    return Scores(
        dimensions=dimensions,
        overall=round(max(0.0, min(1.0, overall)), 3),
        weights=weights,
        notes=notes,
    )
