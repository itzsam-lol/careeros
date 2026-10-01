"""A matching-oriented view of the profile, derived deterministically from verified data."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from careeros.core.enums import EmploymentType, RemotePreference
from careeros.discovery.normalize import extract_countries, normalize_location
from careeros.intelligence.domains import JobDomain, domains_for_text
from careeros.intelligence.extraction import DegreeLevel, degree_levels_in
from careeros.intelligence.functions import JobFunction, title_functions
from careeros.intelligence.skills import canonical_key, extract_skill_names, normalize_skill_name
from careeros.profile.enums import SponsorshipRequirement, VerificationStatus
from careeros.profile.service import ProfileSnapshot

STATUS_WEIGHT = {
    VerificationStatus.VERIFIED: 1.0,
    VerificationStatus.UNVERIFIED: 0.5,
    VerificationStatus.OUTDATED: 0.25,
}
DEGREE_ORDER = [DegreeLevel.DIPLOMA, DegreeLevel.BACHELOR, DegreeLevel.MASTER, DegreeLevel.PHD]


@dataclass
class SkillEvidence:
    name: str
    weight: float
    sources: list[str] = field(default_factory=list)
    verified: bool = False


@dataclass
class MatchProfile:
    profile_id: uuid.UUID
    version: int
    skills: dict[str, SkillEvidence]
    highest_degree: DegreeLevel | None
    pursuing_degree: DegreeLevel | None
    is_student: bool
    expected_graduation_year: int | None
    professional_years: float
    internship_months: float
    authorized_countries: set[str]
    sponsorship_requirement: SponsorshipRequirement
    target_roles: list[str]
    target_domains: set[JobDomain]
    target_countries: set[str]
    target_cities: set[str]
    target_companies: set[str]
    excluded_companies: set[str]
    excluded_keywords: list[str]
    employment_types: set[str]
    remote_preference: RemotePreference
    include_research: bool
    min_compensation: int | None
    compensation_currency: str | None
    has_research: bool
    has_publications: bool
    # Countries where only roles that explicitly offer visa sponsorship are acceptable.
    strict_sponsorship_countries: set[str] = field(default_factory=set)
    # Kinds of work the target roles describe (engineering, data...), to tell a sales role at an
    # AI company apart from an AI engineering role.
    target_functions: set[JobFunction] = field(default_factory=set)
    entry_level_only: bool = False
    hide_unsuitable: bool = False

    def skill(self, name: str) -> SkillEvidence | None:
        return self.skills.get(canonical_key(normalize_skill_name(name)))


def _years_between(start: date | None, end: date | None, today: date) -> float:
    if start is None:
        return 0.0
    finish = end or today
    return max(0.0, (finish - start).days / 365.25)


def _add_skill(
    index: dict[str, SkillEvidence], name: str, weight: float, source: str, verified: bool
) -> None:
    canonical = normalize_skill_name(name)
    key = canonical_key(canonical) or canonical.lower()
    current = index.get(key)
    if current is None:
        index[key] = SkillEvidence(canonical, weight, [source], verified)
        return
    current.weight = max(current.weight, weight)
    current.verified = current.verified or verified
    if source not in current.sources and len(current.sources) < 6:
        current.sources.append(source)


def build_match_profile(snapshot: ProfileSnapshot, *, today: date) -> MatchProfile:
    profile, prefs = snapshot.profile, snapshot.preferences
    skills: dict[str, SkillEvidence] = {}

    for skill in snapshot.skills:
        weight = STATUS_WEIGHT.get(skill.verification_status)
        if weight:
            verified = skill.verification_status == VerificationStatus.VERIFIED
            _add_skill(skills, skill.name, weight, "skills", verified)

    def from_item(
        label: str, status: VerificationStatus, techs: list[str], texts: list[str]
    ) -> None:
        base = STATUS_WEIGHT.get(status)
        if not base:
            return
        verified = status == VerificationStatus.VERIFIED
        for tech in techs:
            _add_skill(skills, tech, 0.9 * base, label, verified)
        for name in extract_skill_names(" ".join(texts)):
            _add_skill(skills, name, 0.8 * base, label, verified)

    for x in snapshot.experience:
        from_item(f"experience:{x.organization}", x.verification_status, x.technologies,
                  [x.description or "", *x.achievements])  # fmt: skip
    for p in snapshot.projects:
        from_item(f"project:{p.name}", p.verification_status, p.technologies,
                  [p.description or "", *p.highlights, p.impact or ""])  # fmt: skip
    for r in snapshot.research:
        from_item(f"research:{r.title[:40]}", r.verification_status, r.technologies,
                  [r.description or "", *r.methods, *r.outcomes, r.title])  # fmt: skip

    # Coursework and the user's own (verified) summary are weaker evidence than hands-on work.
    def from_text(label: str, status: VerificationStatus, texts: list[str], factor: float) -> None:
        base = STATUS_WEIGHT.get(status)
        if not base:
            return
        verified = status == VerificationStatus.VERIFIED
        for name in extract_skill_names(" ".join(texts)):
            _add_skill(skills, name, factor * base, label, verified)

    for e in snapshot.education:
        from_text(f"education:{e.institution}", e.verification_status,
                  [*e.coursework, *e.honors, e.description or "", e.field or ""], 0.8)  # fmt: skip
    from_text("profile summary", profile.basics_status,
              [profile.summary or "", profile.headline or "", profile.current_role or ""], 0.75)  # fmt: skip

    usable_education = [e for e in snapshot.education if e.verification_status in STATUS_WEIGHT]
    highest: DegreeLevel | None = None
    pursuing: DegreeLevel | None = None
    graduation_year: int | None = None
    for education in usable_education:
        levels = degree_levels_in(education.degree)
        if not levels:
            continue
        level = max(levels, key=DEGREE_ORDER.index)
        ongoing = education.is_current or (
            education.end_date is not None and education.end_date > today
        )
        if ongoing:
            pursuing = level if pursuing is None else max(pursuing, level, key=DEGREE_ORDER.index)
            if education.end_date:
                graduation_year = education.end_date.year
        else:
            highest = level if highest is None else max(highest, level, key=DEGREE_ORDER.index)

    professional = 0.0
    internship_months = 0.0
    for x in snapshot.experience:
        if x.verification_status not in STATUS_WEIGHT:
            continue
        years = _years_between(x.start_date, None if x.is_current else x.end_date, today)
        if x.employment_type in (EmploymentType.INTERNSHIP, EmploymentType.APPRENTICESHIP):
            internship_months += years * 12
        elif x.employment_type == EmploymentType.PART_TIME:
            professional += years * 0.5
        elif x.employment_type in (None, EmploymentType.FULL_TIME, EmploymentType.CONTRACT,
                                   EmploymentType.FREELANCE, EmploymentType.RESEARCH):  # fmt: skip
            professional += years

    target_domains: set[JobDomain] = set()
    for text in [*prefs.target_roles, *prefs.target_technologies]:
        target_domains |= domains_for_text(text)

    authorized = set(extract_countries(profile.authorized_countries))
    return MatchProfile(
        profile_id=profile.id,
        version=profile.version,
        skills=skills,
        highest_degree=highest,
        pursuing_degree=pursuing,
        is_student=pursuing is not None,
        expected_graduation_year=graduation_year,
        professional_years=round(professional, 2),
        internship_months=round(internship_months, 1),
        authorized_countries=authorized,
        sponsorship_requirement=profile.sponsorship_requirement,
        target_roles=list(prefs.target_roles),
        target_functions={f for role in prefs.target_roles for f in title_functions(role)},
        entry_level_only=prefs.entry_level_only,
        hide_unsuitable=prefs.hide_unsuitable,
        target_domains=target_domains,
        target_countries=set(extract_countries(prefs.target_countries))
        | {c.strip() for c in prefs.target_countries if c.strip()},
        target_cities={normalize_location(c) for c in prefs.target_cities if c.strip()},
        strict_sponsorship_countries=set(
            extract_countries(prefs.sponsorship_required_countries or [])
        ),
        target_companies={c.strip().lower() for c in prefs.target_companies if c.strip()},
        excluded_companies={c.strip().lower() for c in prefs.excluded_companies if c.strip()},
        excluded_keywords=[k.strip().lower() for k in prefs.excluded_keywords if k.strip()],
        employment_types=set(prefs.employment_types),
        remote_preference=prefs.remote_preference,
        include_research=prefs.include_research,
        min_compensation=prefs.min_compensation,
        compensation_currency=prefs.compensation_currency,
        has_research=any(
            r.verification_status == VerificationStatus.VERIFIED for r in snapshot.research
        ),
        has_publications=any(
            p.verification_status == VerificationStatus.VERIFIED for p in snapshot.publications
        ),
    )
