"""Derive atomic, citable career facts from structured profile items.

Resume bullets, outreach sentences and application answers cite these facts. Derived facts are
re-synchronised whenever their source item changes:

* unchanged statements keep their id (so existing citations stay valid),
* new statements are added, removed ones deleted,
* verification follows the source item, except that a fact the user explicitly REJECTED stays
  rejected.
"""

from __future__ import annotations

import hashlib
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.profile.enums import FactCategory, FactOrigin, VerificationStatus
from careeros.profile.models import (
    Achievement,
    CareerFact,
    Education,
    Experience,
    Project,
    Publication,
    ResearchExperience,
)


@dataclass(frozen=True, slots=True)
class DerivedFact:
    category: FactCategory
    fact: str
    context: str | None
    source_field: str


def month(value: date | None) -> str | None:
    return value.strftime("%b %Y") if value else None


def period(start: date | None, end: date | None, is_current: bool = False) -> str | None:
    first = month(start)
    last = "Present" if is_current else month(end)
    if first and last:
        return f"{first} – {last}"
    return first or last


def _clean(text: str | None) -> str | None:
    if text is None:
        return None
    collapsed = " ".join(text.split())
    return collapsed or None


def fact_hash(entity: str, field: str, text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(f"{entity}|{field}|{normalized}".encode()).hexdigest()


def _education(item: Education) -> list[DerivedFact]:
    facts: list[DerivedFact] = []
    ctx = f"{item.degree} at {item.institution}"
    when = period(item.start_date, item.end_date, item.is_current)
    degree = f"{item.degree}{f' in {item.field}' if item.field else ''}, {item.institution}"
    facts.append(
        DerivedFact(
            FactCategory.EDUCATION, f"{degree}{f' ({when})' if when else ''}", ctx, "degree"
        )
    )
    if item.gpa:
        facts.append(DerivedFact(FactCategory.EDUCATION, f"GPA {item.gpa} ({ctx})", ctx, "gpa"))
    if (description := _clean(item.description)) is not None:
        facts.append(DerivedFact(FactCategory.EDUCATION, description, ctx, "description"))
    if item.coursework:
        courses = ", ".join(item.coursework)
        facts.append(
            DerivedFact(FactCategory.EDUCATION, f"Coursework: {courses}", ctx, "coursework")
        )
    facts.extend(DerivedFact(FactCategory.ACHIEVEMENT, h, ctx, "honors") for h in item.honors)
    return facts


def _experience(item: Experience) -> list[DerivedFact]:
    ctx = f"{item.role} at {item.organization}"
    when = period(item.start_date, item.end_date, item.is_current)
    facts = [
        DerivedFact(FactCategory.EXPERIENCE, f"{ctx}{f' ({when})' if when else ''}", ctx, "role")
    ]
    if (description := _clean(item.description)) is not None:
        facts.append(DerivedFact(FactCategory.EXPERIENCE, description, ctx, "description"))
    facts.extend(
        DerivedFact(FactCategory.EXPERIENCE, a, ctx, "achievements") for a in item.achievements
    )
    if item.technologies:
        techs = ", ".join(item.technologies)
        facts.append(DerivedFact(FactCategory.SKILL, f"Used {techs} as {ctx}", ctx, "technologies"))
    return facts


def _project(item: Project) -> list[DerivedFact]:
    ctx = f"Project: {item.name}"
    facts: list[DerivedFact] = []
    if (description := _clean(item.description)) is not None:
        facts.append(
            DerivedFact(FactCategory.PROJECT, f"{item.name}: {description}", ctx, "description")
        )
    else:
        facts.append(DerivedFact(FactCategory.PROJECT, f"Built {item.name}", ctx, "name"))
    facts.extend(DerivedFact(FactCategory.PROJECT, h, ctx, "highlights") for h in item.highlights)
    if (impact := _clean(item.impact)) is not None:
        facts.append(DerivedFact(FactCategory.PROJECT, impact, ctx, "impact"))
    facts.extend(DerivedFact(FactCategory.METRIC, m, ctx, "metrics") for m in item.metrics)
    if item.technologies:
        techs = ", ".join(item.technologies)
        facts.append(
            DerivedFact(FactCategory.SKILL, f"Built {item.name} using {techs}", ctx, "technologies")
        )
    return facts


def _research(item: ResearchExperience) -> list[DerivedFact]:
    ctx = f"Research: {item.title} ({item.organization})"
    supervisor = f", supervised by {item.supervisor}" if item.supervisor else ""
    when = period(item.start_date, item.end_date, item.is_current)
    facts = [
        DerivedFact(
            FactCategory.RESEARCH,
            f"Research on {item.title} at {item.organization}{supervisor}{f' ({when})' if when else ''}",
            ctx,
            "title",
        )
    ]
    if (description := _clean(item.description)) is not None:
        facts.append(DerivedFact(FactCategory.RESEARCH, description, ctx, "description"))
    if item.methods:
        facts.append(
            DerivedFact(
                FactCategory.RESEARCH, f"Methods: {', '.join(item.methods)}", ctx, "methods"
            )
        )
    if item.technologies:
        techs = ", ".join(item.technologies)
        facts.append(
            DerivedFact(
                FactCategory.SKILL, f"Used {techs} in research on {item.title}", ctx, "technologies"
            )
        )
    facts.extend(DerivedFact(FactCategory.RESEARCH, o, ctx, "outcomes") for o in item.outcomes)
    return facts


def _publication(item: Publication) -> list[DerivedFact]:
    ctx = f"Publication: {item.title}"
    authors = ", ".join(item.authors)
    venue = f" {item.venue}," if item.venue else ""
    year = f" {item.year}" if item.year else ""
    status = item.status.value.replace("_", " ").lower()
    citation = f'{authors + ". " if authors else ""}"{item.title}".{venue}{year} ({status})'
    facts = [DerivedFact(FactCategory.PUBLICATION, " ".join(citation.split()), ctx, "citation")]
    if (summary := _clean(item.summary)) is not None:
        facts.append(DerivedFact(FactCategory.PUBLICATION, summary, ctx, "summary"))
    return facts


def _achievement(item: Achievement) -> list[DerivedFact]:
    ctx = f"{item.kind.value.title()}: {item.title}"
    org = f" — {item.organization}" if item.organization else ""
    when = f" ({month(item.achieved_on)})" if item.achieved_on else ""
    facts = [DerivedFact(FactCategory.ACHIEVEMENT, f"{item.title}{org}{when}", ctx, "title")]
    if (description := _clean(item.description)) is not None:
        facts.append(DerivedFact(FactCategory.ACHIEVEMENT, description, ctx, "description"))
    return facts


DERIVERS: dict[str, Callable[[Any], list[DerivedFact]]] = {
    "education": _education,
    "experience": _experience,
    "project": _project,
    "research": _research,
    "publication": _publication,
    "achievement": _achievement,
}


async def sync_derived_facts(
    session: AsyncSession, profile_id: uuid.UUID, entity: str, item: Any
) -> list[CareerFact]:
    derive = DERIVERS.get(entity)
    if derive is None:
        return []
    wanted = derive(item)
    existing = (
        await session.execute(
            select(CareerFact).where(
                CareerFact.profile_id == profile_id,
                CareerFact.source_entity == entity,
                CareerFact.source_id == item.id,
                CareerFact.origin == FactOrigin.DERIVED,
            )
        )
    ).scalars()
    by_hash = {fact.content_hash: fact for fact in existing}
    kept: list[CareerFact] = []
    seen: set[str] = set()
    for index, derived in enumerate(wanted):
        digest = fact_hash(entity, derived.source_field, derived.fact)
        if digest in seen:
            continue
        seen.add(digest)
        fact = by_hash.get(digest)
        if fact is None:
            fact = CareerFact(
                profile_id=profile_id,
                category=derived.category,
                fact=derived.fact,
                context=derived.context,
                source_entity=entity,
                source_id=item.id,
                source_field=derived.source_field,
                origin=FactOrigin.DERIVED,
                content_hash=digest,
                confidence=1.0,
                source=item.source,
            )
            session.add(fact)
        fact.context = derived.context
        fact.sort_order = index
        if fact.verification_status != VerificationStatus.REJECTED:
            fact.verification_status = item.verification_status
            fact.verified_at = item.verified_at
        kept.append(fact)
    for digest, fact in by_hash.items():
        if digest not in seen:
            await session.delete(fact)
    return kept


async def delete_derived_facts(
    session: AsyncSession, profile_id: uuid.UUID, entity: str, item_ids: Sequence[uuid.UUID]
) -> None:
    await session.execute(
        delete(CareerFact).where(
            CareerFact.profile_id == profile_id,
            CareerFact.source_entity == entity,
            CareerFact.source_id.in_(list(item_ids)),
            CareerFact.origin == FactOrigin.DERIVED,
        )
    )
