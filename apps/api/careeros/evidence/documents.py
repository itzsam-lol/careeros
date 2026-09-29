"""Turn profile items into retrievable text documents."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from careeros.core.crypto import sha256_hex
from careeros.profile.enums import FactOrigin, VerificationStatus
from careeros.profile.facts import month, period
from careeros.profile.service import ProfileSnapshot


@dataclass(frozen=True, slots=True)
class EvidenceDocument:
    source_type: str
    source_id: uuid.UUID
    title: str
    content: str
    verification_status: VerificationStatus

    @property
    def content_hash(self) -> str:
        return sha256_hex(f"{self.title}\n{self.content}")


def _join(*parts: str | None) -> str:
    return " ".join(p.strip() for p in parts if p and p.strip())


def _list(label: str, values: list[str]) -> str | None:
    return f"{label}: {'; '.join(values)}." if values else None


def build_documents(snapshot: ProfileSnapshot) -> list[EvidenceDocument]:
    """All evidence documents for a profile. Rejected items never become evidence."""
    docs: list[EvidenceDocument] = []

    def add(
        source_type: str, item_id: uuid.UUID, title: str, content: str, status: VerificationStatus
    ) -> None:
        if status == VerificationStatus.REJECTED or not content.strip():
            return
        docs.append(EvidenceDocument(source_type, item_id, title[:300], content, status))

    for p in snapshot.projects:
        add("project", p.id, f"Project: {p.name}", _join(
            f"Project {p.name}.", p.role and f"Role: {p.role}.", p.description,
            _list("Highlights", p.highlights), p.impact and f"Impact: {p.impact}",
            _list("Metrics", p.metrics), _list("Technologies", p.technologies),
        ), p.verification_status)  # fmt: skip
    for x in snapshot.experience:
        when = period(x.start_date, x.end_date, x.is_current)
        add("experience", x.id, f"{x.role} at {x.organization}", _join(
            f"{x.role} at {x.organization}{f' ({when})' if when else ''}.", x.description,
            _list("Achievements", x.achievements), _list("Technologies", x.technologies),
        ), x.verification_status)  # fmt: skip
    for r in snapshot.research:
        add("research", r.id, f"Research: {r.title}", _join(
            f"Research on {r.title} at {r.organization}.",
            r.supervisor and f"Supervisor: {r.supervisor}.", r.description,
            _list("Methods", r.methods), _list("Outcomes", r.outcomes),
            _list("Technologies", r.technologies),
        ), r.verification_status)  # fmt: skip
    for pub in snapshot.publications:
        add("publication", pub.id, f"Publication: {pub.title}", _join(
            f"Publication: {pub.title}.", pub.venue and f"Venue: {pub.venue}.",
            str(pub.year) if pub.year else None, pub.summary,
        ), pub.verification_status)  # fmt: skip
    for e in snapshot.education:
        when = period(e.start_date, e.end_date, e.is_current)
        add("education", e.id, f"{e.degree}, {e.institution}", _join(
            f"{e.degree}{f' in {e.field}' if e.field else ''} at {e.institution}"
            f"{f' ({when})' if when else ''}.", e.gpa and f"GPA {e.gpa}.", e.description,
            _list("Coursework", e.coursework), _list("Honors", e.honors),
        ), e.verification_status)  # fmt: skip
    for a in snapshot.achievements:
        add("achievement", a.id, f"{a.kind.value.title()}: {a.title}", _join(
            f"{a.title}.", a.organization and f"Organization: {a.organization}.",
            month(a.achieved_on), a.description,
        ), a.verification_status)  # fmt: skip
    for fact in snapshot.facts:
        if fact.origin == FactOrigin.USER:
            add(
                "career_fact",
                fact.id,
                f"Fact: {fact.fact[:80]}",
                fact.fact,
                fact.verification_status,
            )

    usable_skills = [
        s for s in snapshot.skills if s.verification_status != VerificationStatus.REJECTED
    ]
    if usable_skills:
        verified = all(s.verification_status == VerificationStatus.VERIFIED for s in usable_skills)
        summary = "; ".join(
            s.name + (f" ({s.proficiency.value.lower()})" if s.proficiency else "")
            for s in usable_skills
        )
        add(
            "skills",
            snapshot.profile.id,
            "Skills",
            f"Skills: {summary}.",
            VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED,
        )
    return docs
