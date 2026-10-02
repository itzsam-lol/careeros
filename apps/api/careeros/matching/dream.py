"""Dream companies: every fresher role there gets a ready-to-apply kit and an alert.

The user lists them in their preferences ("Dream companies", `target_companies`). Names match on
whole leading words of the normalised company name, so "Amazon" covers "Amazon Web Services"
and "NatWest" covers "NatWest Group", while "Meta" does not match "Metadata Inc".
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

from careeros.core.enums import EmploymentType, SeniorityLevel
from careeros.discovery.normalize import detect_seniority, normalize_company

if TYPE_CHECKING:
    from careeros.jobs.models import Job
    from careeros.matching.models import JobMatch

_FRESHER_LEVELS = {SeniorityLevel.INTERN, SeniorityLevel.ENTRY}
_FRESHER_TYPES = {EmploymentType.INTERNSHIP, EmploymentType.APPRENTICESHIP}


def is_dream_company(company: str, dream_companies: Iterable[str]) -> bool:
    words = normalize_company(company).split()
    for name in dream_companies:
        wanted = normalize_company(name).split()
        if wanted and words[: len(wanted)] == wanted:
            return True
    return False


def is_fresher_role(job: Job, match: JobMatch) -> bool:
    """Intern or entry level, an internship, or open to the user's graduation year."""
    level = job.seniority
    if level == SeniorityLevel.UNKNOWN:
        level = detect_seniority(job.title, job.employment_type)
    if level in _FRESHER_LEVELS or job.employment_type in _FRESHER_TYPES:
        return True
    return any(
        check.get("key") == "graduation_year" and check.get("status") == "PASS"
        for check in match.eligibility or []
    )


def wants_application_kit(job: Job, match: JobMatch, dream_companies: Iterable[str]) -> bool:
    return (
        match.eligible
        and job.is_active
        and is_dream_company(job.company, dream_companies)
        and is_fresher_role(job, match)
    )
