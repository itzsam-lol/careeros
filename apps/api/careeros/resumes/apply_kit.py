"""Apply kit: everything needed to apply to one job, in one place.

Built only from the verified profile and the job: copy-ready answers to the questions application
forms ask, the documents generated for this job, and a short "Why this company?" draft the user
edits. Nothing is submitted anywhere; the user applies on the employer's site.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from careeros.jobs.models import Job
from careeros.profile.enums import SponsorshipRequirement, VerificationStatus
from careeros.profile.service import ProfileSnapshot
from careeros.resumes import tailor as tailoring
from careeros.resumes.service import _and_list, evidence_stories, student_phrase

_VERIFIED = VerificationStatus.VERIFIED


@dataclass
class KitField:
    label: str
    value: str


@dataclass
class KitAnswer:
    question: str
    answer: str


@dataclass
class ApplyKit:
    apply_url: str | None
    platform: str
    fields: list[KitField] = field(default_factory=list)
    answers: list[KitAnswer] = field(default_factory=list)
    why_company: str = ""
    missing: list[str] = field(default_factory=list)


def _authorisation(snapshot: ProfileSnapshot, job: Job) -> str | None:
    profile = snapshot.profile
    authorised = set(profile.authorized_countries or [])
    countries = [c for c in job.countries or [] if c]
    if not countries:
        return profile.work_authorization or None
    allowed = [c for c in countries if c in authorised]
    if allowed:
        return f"Yes, I am authorised to work in {_and_list(allowed)} and do not need sponsorship."
    if profile.sponsorship_requirement == SponsorshipRequirement.REQUIRED:
        return f"I will need visa sponsorship to work in {_and_list(countries)}."
    if profile.sponsorship_requirement == SponsorshipRequirement.NOT_REQUIRED:
        return f"I do not need visa sponsorship to work in {_and_list(countries)}."
    return profile.work_authorization or None


def _why_company(snapshot: ProfileSnapshot, job: Job, extraction: dict[str, Any]) -> str:
    target = tailoring.JobTarget.from_extraction(
        job.title, job.company, extraction, job.description or ""
    )
    stories = evidence_stories(snapshot, target)
    mine = {
        tailoring.canonical_key(s.name)
        for s in snapshot.skills
        if s.verification_status == _VERIFIED
    }
    wanted = [*target.required_skills, *target.preferred_skills]
    shared = [s for s in dict.fromkeys(wanted) if tailoring.canonical_key(s) in mine][:3]
    education = next((e for e in snapshot.education if e.verification_status == _VERIFIED), None)
    who = f"As {student_phrase(education)}, " if education else ""
    lines = [
        f"{who}I'm applying for the {job.title} role at {job.company} because it is the kind of work I want to grow in."
    ]
    if shared:
        lines.append(f"It asks for {_and_list(shared)}, which I have used in my own work.")
    if stories:
        story = stories[0]
        text = story.text.rstrip(".")
        lines.append(
            f"{story.context[0].upper()}{story.context[1:]}, I {text[0].lower()}{text[1:]}."
        )
    lines.append(
        f"I'd bring the same care to {job.company}'s team. [Add one specific reason you want to join {job.company}.]"
    )
    return " ".join(lines)


def build_apply_kit(
    snapshot: ProfileSnapshot, job: Job, extraction: dict[str, Any], account_email: str
) -> ApplyKit:
    profile = snapshot.profile
    education = next((e for e in snapshot.education if e.verification_status == _VERIFIED), None)
    fields: list[KitField] = []

    def add(label: str, value: str | None) -> None:
        if value and value.strip():
            fields.append(KitField(label, value.strip()))

    add("Full name", profile.full_name)
    add("Email", profile.contact_email or account_email)
    add("Phone", profile.phone)
    add("Current location", profile.location)
    add("LinkedIn", profile.linkedin_url)
    add("GitHub", profile.github_url)
    add("Portfolio", profile.portfolio_url)
    if education:
        add("University", education.institution)
        add("Degree", f"{education.degree}{f' in {education.field}' if education.field else ''}")
        if education.end_date:
            add("Graduation", education.end_date.strftime("%B %Y"))
        add("CGPA", education.gpa)
    add("Work authorisation", _authorisation(snapshot, job))
    add(
        "Availability",
        profile.availability
        or (
            f"From {profile.earliest_start_date:%d %B %Y}" if profile.earliest_start_date else None
        ),
    )

    answers = [
        KitAnswer(a.question, a.answer)
        for a in snapshot.answers
        if a.verification_status == _VERIFIED
    ]
    missing = [
        label
        for label, present in (
            ("phone number", profile.phone),
            ("LinkedIn URL", profile.linkedin_url),
            ("graduation date", education and education.end_date),
            ("availability or start date", profile.availability or profile.earliest_start_date),
        )
        if not present
    ]
    return ApplyKit(
        apply_url=job.application_url or job.canonical_url,
        platform=job.application_platform.value,
        fields=fields,
        answers=answers,
        why_company=_why_company(snapshot, job, extraction),
        missing=missing,
    )
