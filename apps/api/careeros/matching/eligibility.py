"""Hard eligibility checks. Each check is PASS, FAIL or UNKNOWN with a human reason."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any

from careeros.core.enums import EmploymentType, RemotePreference, RemoteType, SeniorityLevel
from careeros.discovery.normalize import detect_seniority, normalize_location
from careeros.intelligence.extraction import JobExtraction, Sponsorship
from careeros.jobs.models import Job
from careeros.matching.profile_view import DEGREE_ORDER, MatchProfile
from careeros.profile.enums import SponsorshipRequirement

# Entry-level feeds: roles at these levels, or asking for more than this many years, are out.
_EXPERIENCED_LEVELS = frozenset(
    {SeniorityLevel.MID, SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.MANAGER}
)
ENTRY_MAX_YEARS = 2.0


class CheckStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 - a check outcome, not a password
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class EligibilityCheck:
    key: str
    label: str
    status: CheckStatus
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "status": self.status.value}


def _fmt_types(values: set[str]) -> str:
    return ", ".join(sorted(v.replace("_", " ").lower() for v in values))


def _location_check(job: Job, mp: MatchProfile) -> EligibilityCheck | None:
    label = "Location"
    if job.remote_type == RemoteType.REMOTE:
        # "Remote, Turkey" is remote for people in Turkey, not for everyone.
        restricted = set(job.countries)
        allowed = mp.target_countries | mp.authorized_countries
        if restricted and allowed and not restricted & allowed:
            where = ", ".join(sorted(restricted))
            return EligibilityCheck(
                "location", label, CheckStatus.FAIL, f"Remote, but only for people based in {where}"
            )
        if mp.remote_preference == RemotePreference.ONSITE:
            return EligibilityCheck(
                "location",
                label,
                CheckStatus.PASS,
                "Remote role (you prefer on-site, but it is open to you)",
            )
        return EligibilityCheck("location", label, CheckStatus.PASS, "Remote role")
    if not (mp.target_countries or mp.target_cities):
        if mp.remote_preference == RemotePreference.REMOTE and job.remote_type == RemoteType.ONSITE:
            return EligibilityCheck(
                "location", label, CheckStatus.FAIL, "On-site role; you only want remote work"
            )
        return None
    where = job.location or ", ".join(job.locations)
    if not where and not job.countries:
        return EligibilityCheck(
            "location", label, CheckStatus.UNKNOWN, "The posting does not state a location"
        )
    normalized = normalize_location(where)
    if any(city and city in normalized for city in mp.target_cities):
        return EligibilityCheck(
            "location", label, CheckStatus.PASS, f"{where} is one of your target cities"
        )
    if mp.target_countries & set(job.countries):
        countries = ", ".join(sorted(mp.target_countries & set(job.countries)))
        return EligibilityCheck(
            "location", label, CheckStatus.PASS, f"In {countries}, one of your target countries"
        )
    if mp.remote_preference == RemotePreference.REMOTE:
        return EligibilityCheck(
            "location", label, CheckStatus.FAIL, f"{where} is not remote; you only want remote work"
        )
    return EligibilityCheck(
        "location", label, CheckStatus.FAIL, f"{where} is outside your target locations"
    )


def _authorization_check(job: Job, ex: JobExtraction, mp: MatchProfile) -> EligibilityCheck | None:
    label = "Work authorization"
    countries = set(ex.work_authorization_countries) or set(job.countries)
    if not countries:
        if (
            ex.sponsorship == Sponsorship.NOT_AVAILABLE
            and mp.sponsorship_requirement == SponsorshipRequirement.REQUIRED
        ):
            return EligibilityCheck("work_authorization", label, CheckStatus.UNKNOWN,
                                    "The posting does not sponsor visas and its country is unclear")  # fmt: skip
        return None
    where = ", ".join(sorted(countries))
    if countries & mp.authorized_countries:
        return EligibilityCheck(
            "work_authorization", label, CheckStatus.PASS, f"You are authorised to work in {where}"
        )
    if mp.sponsorship_requirement == SponsorshipRequirement.NOT_REQUIRED:
        return EligibilityCheck(
            "work_authorization",
            label,
            CheckStatus.PASS,
            "You indicated you do not need sponsorship",
        )
    strict = countries & mp.strict_sponsorship_countries
    # Reached only when none of the countries is one the user may already work in.
    if strict and strict == countries and ex.sponsorship != Sponsorship.AVAILABLE:
        # The user only wants roles here that explicitly offer a visa ("not stated" is not enough).
        return EligibilityCheck("work_authorization", label, CheckStatus.FAIL,
                                f"Based in {where}; the posting does not offer visa sponsorship")  # fmt: skip
    if ex.sponsorship == Sponsorship.NOT_AVAILABLE:
        return EligibilityCheck("work_authorization", label, CheckStatus.FAIL,
                                f"Requires authorisation to work in {where} and does not sponsor visas")  # fmt: skip
    if ex.sponsorship == Sponsorship.AVAILABLE:
        return EligibilityCheck(
            "work_authorization",
            label,
            CheckStatus.PASS,
            f"Based in {where}; visa sponsorship is available",
        )
    if not mp.authorized_countries and mp.sponsorship_requirement == SponsorshipRequirement.UNKNOWN:
        return EligibilityCheck("work_authorization", label, CheckStatus.UNKNOWN,
                                f"Based in {where}; add your work authorisation to your profile to check this")  # fmt: skip
    return EligibilityCheck("work_authorization", label, CheckStatus.UNKNOWN,
                            f"Based in {where}; the posting does not say whether it sponsors visas")  # fmt: skip


def _experience_checks(job: Job, ex: JobExtraction, mp: MatchProfile) -> list[EligibilityCheck]:
    checks: list[EligibilityCheck] = []
    have = mp.professional_years
    if ex.min_years_experience:
        need = ex.min_years_experience
        if have + 0.5 >= need:
            checks.append(EligibilityCheck("experience", "Experience", CheckStatus.PASS,
                                           f"Requires {need:g}+ years; you have about {have:.1f}"))  # fmt: skip
        elif need - have >= 2:
            checks.append(EligibilityCheck("experience", "Experience", CheckStatus.FAIL,
                                           f"Requires {need:g}+ years of experience; your profile shows about {have:.1f}"))  # fmt: skip
        else:
            checks.append(EligibilityCheck("experience", "Experience", CheckStatus.UNKNOWN,
                                           f"Requires {need:g}+ years; you have about {have:.1f}"))  # fmt: skip
    if mp.entry_level_only:
        level = job.seniority
        if level == SeniorityLevel.UNKNOWN:
            level = detect_seniority(job.title, job.employment_type)
        if level in _EXPERIENCED_LEVELS:
            checks.append(EligibilityCheck("seniority", "Seniority", CheckStatus.FAIL,
                                           f"{level.value.title()}-level role; you only want intern, graduate and entry-level roles"))  # fmt: skip
            return checks
        if ex.min_years_experience and ex.min_years_experience > ENTRY_MAX_YEARS:
            if not any(c.key == "experience" and c.status == CheckStatus.FAIL for c in checks):
                checks.append(EligibilityCheck("experience", "Experience", CheckStatus.FAIL,
                                               f"Requires {ex.min_years_experience:g}+ years; you only want entry-level roles"))  # fmt: skip
            return checks
    level = job.seniority
    if level == SeniorityLevel.UNKNOWN:
        level = detect_seniority(job.title, job.employment_type)
    senior = level in (SeniorityLevel.SENIOR, SeniorityLevel.LEAD, SeniorityLevel.MANAGER)
    if senior and have < 3 and not any(c.status == CheckStatus.FAIL for c in checks):
        checks.append(EligibilityCheck("seniority", "Seniority", CheckStatus.FAIL,
                                       f"{level.value.title()}-level role; your profile shows about {have:.1f} years of professional experience"))  # fmt: skip
    return checks


def _education_checks(ex: JobExtraction, mp: MatchProfile) -> list[EligibilityCheck]:
    checks: list[EligibilityCheck] = []
    if ex.requires_current_student:
        if mp.is_student:
            checks.append(
                EligibilityCheck(
                    "student_status",
                    "Student status",
                    CheckStatus.PASS,
                    "Requires current enrolment; you are enrolled",
                )
            )
        else:
            checks.append(
                EligibilityCheck(
                    "student_status",
                    "Student status",
                    CheckStatus.FAIL,
                    "Requires current enrolment in a degree programme",
                )
            )
    if ex.graduation_years:
        years = ", ".join(str(y) for y in ex.graduation_years)
        if mp.expected_graduation_year is None:
            checks.append(
                EligibilityCheck(
                    "graduation_year",
                    "Graduation year",
                    CheckStatus.UNKNOWN,
                    f"Open to {years} graduates; add your expected graduation date",
                )
            )
        elif mp.expected_graduation_year in ex.graduation_years:
            checks.append(
                EligibilityCheck(
                    "graduation_year",
                    "Graduation year",
                    CheckStatus.PASS,
                    f"You graduate in {mp.expected_graduation_year}",
                )
            )
        else:
            checks.append(
                EligibilityCheck(
                    "graduation_year",
                    "Graduation year",
                    CheckStatus.FAIL,
                    f"Open to {years} graduates; you graduate in {mp.expected_graduation_year}",
                )
            )
    if ex.degree_levels:
        user_levels = [lvl for lvl in (mp.highest_degree, mp.pursuing_degree) if lvl is not None]
        if not user_levels:
            checks.append(
                EligibilityCheck(
                    "degree",
                    "Degree",
                    CheckStatus.UNKNOWN,
                    "Add your education to check degree requirements",
                )
            )
        else:
            best = max(DEGREE_ORDER.index(level) for level in user_levels)
            lowest_required = min(ex.degree_levels, key=DEGREE_ORDER.index)
            if DEGREE_ORDER.index(lowest_required) <= best:
                checks.append(
                    EligibilityCheck(
                        "degree",
                        "Degree",
                        CheckStatus.PASS,
                        f"Meets the {lowest_required.value.lower()} degree requirement",
                    )
                )
            else:
                checks.append(
                    EligibilityCheck(
                        "degree",
                        "Degree",
                        CheckStatus.FAIL,
                        f"Requires a {lowest_required.value.lower()} degree or higher",
                    )
                )
    return checks  # fmt: skip


def evaluate_eligibility(
    job: Job, ex: JobExtraction, mp: MatchProfile, *, now: datetime
) -> list[EligibilityCheck]:
    checks: list[EligibilityCheck] = []
    if not job.is_active:
        checks.append(
            EligibilityCheck("status", "Posting", CheckStatus.FAIL, "This posting is closed")
        )
    if job.deadline and job.deadline < now:
        checks.append(
            EligibilityCheck(
                "deadline",
                "Deadline",
                CheckStatus.FAIL,
                f"The deadline passed on {job.deadline:%d %b %Y}",
            )
        )
    if job.company.strip().lower() in mp.excluded_companies:
        checks.append(
            EligibilityCheck(
                "exclusions", "Your exclusions", CheckStatus.FAIL, f"You excluded {job.company}"
            )
        )
    for keyword in mp.excluded_keywords:
        if re.search(rf"\b{re.escape(keyword)}\b", job.title, re.IGNORECASE):
            checks.append(
                EligibilityCheck(
                    "exclusions",
                    "Your exclusions",
                    CheckStatus.FAIL,
                    f"Title contains '{keyword}', which you excluded",
                )
            )
            break
    kind = ex.employment_type or job.employment_type
    if mp.employment_types and kind is not None:
        allowed = set(mp.employment_types)
        if kind == EmploymentType.RESEARCH and mp.include_research:
            allowed.add(EmploymentType.RESEARCH.value)
        if kind.value in allowed:
            checks.append(
                EligibilityCheck(
                    "employment_type",
                    "Role type",
                    CheckStatus.PASS,
                    f"{kind.value.replace('_', ' ').title()} role, as you want",
                )
            )
        else:
            checks.append(
                EligibilityCheck(
                    "employment_type",
                    "Role type",
                    CheckStatus.FAIL,
                    f"This is a {kind.value.replace('_', '-').lower()} role; you are looking for {_fmt_types(allowed)}",
                )
            )
    for check in (_location_check(job, mp), _authorization_check(job, ex, mp)):
        if check is not None:
            checks.append(check)
    checks.extend(_experience_checks(job, ex, mp))
    checks.extend(_education_checks(ex, mp))
    return checks  # fmt: skip


def is_eligible(checks: list[EligibilityCheck]) -> bool:
    return not any(check.status == CheckStatus.FAIL for check in checks)
