"""Profile business logic. Never commits: callers own the unit of work."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.core.errors import ConflictError, NotFoundError, ValidationFailedError
from careeros.intelligence.skills import canonical_key, normalize_skill_name, skill_category
from careeros.profile import facts as fact_sync
from careeros.profile.enums import (
    FactOrigin,
    ItemSource,
    SponsorshipRequirement,
    VerificationStatus,
)
from careeros.profile.models import (
    Achievement,
    CareerFact,
    CareerPreferences,
    Education,
    Experience,
    ProfessionalProfile,
    ProfileItem,
    Project,
    Publication,
    ResearchExperience,
    ReusableAnswer,
    Skill,
)
from careeros.profile.schemas import ChecklistItem, PreferencesIn, ProfileBasicsIn, ProfileStats
from careeros.profile.sections import SECTIONS, Section
from careeros.users.models import User


@dataclass
class ProfileSnapshot:
    profile: ProfessionalProfile
    preferences: CareerPreferences
    education: list[Education] = field(default_factory=list)
    experience: list[Experience] = field(default_factory=list)
    projects: list[Project] = field(default_factory=list)
    research: list[ResearchExperience] = field(default_factory=list)
    publications: list[Publication] = field(default_factory=list)
    skills: list[Skill] = field(default_factory=list)
    achievements: list[Achievement] = field(default_factory=list)
    facts: list[CareerFact] = field(default_factory=list)
    answers: list[ReusableAnswer] = field(default_factory=list)

    def items(self) -> list[ProfileItem]:
        groups: list[list[Any]] = [
            self.education, self.experience, self.projects, self.research,
            self.publications, self.skills, self.achievements, self.answers,
        ]  # fmt: skip
        return [item for group in groups for item in group]


def bump_version(profile: ProfessionalProfile) -> None:
    profile.version = (profile.version or 0) + 1
    profile.updated_at = utcnow()


async def get_profile(session: AsyncSession, user: User) -> ProfessionalProfile | None:
    return (
        await session.execute(
            select(ProfessionalProfile).where(ProfessionalProfile.user_id == user.id)
        )
    ).scalar_one_or_none()


async def get_or_create_profile(session: AsyncSession, user: User) -> ProfessionalProfile:
    profile = await get_profile(session, user)
    if profile is not None:
        return profile
    now = utcnow()
    await session.execute(
        pg_insert(ProfessionalProfile)
        .values(
            id=uuid.uuid4(),
            user_id=user.id,
            full_name=user.name,
            contact_email=user.email,
            other_links=[],
            authorized_countries=[],
            sponsorship_requirement=SponsorshipRequirement.UNKNOWN,
            basics_status=VerificationStatus.VERIFIED,
            version=1,
            indexed_version=0,
            created_at=now,
            updated_at=now,
        )
        .on_conflict_do_nothing(index_elements=["user_id"])
    )
    profile = await get_profile(session, user)
    if profile is None:  # pragma: no cover - guarded by the insert above
        raise NotFoundError("Profile could not be created")
    return profile


async def get_preferences(session: AsyncSession, profile: ProfessionalProfile) -> CareerPreferences:
    prefs = (
        await session.execute(
            select(CareerPreferences).where(CareerPreferences.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if prefs is None:
        prefs = CareerPreferences(profile_id=profile.id)
        session.add(prefs)
        await session.flush()
    return prefs


async def load_snapshot(session: AsyncSession, profile: ProfessionalProfile) -> ProfileSnapshot:
    snapshot = ProfileSnapshot(profile=profile, preferences=await get_preferences(session, profile))
    for key, section in SECTIONS.items():
        rows = await list_items(session, profile, section)
        setattr(snapshot, key, rows)
    return snapshot


def _order_columns(section: Section) -> list[Any]:
    model: Any = section.model
    columns: list[Any] = [model.sort_order]
    for name in ("end_date", "achieved_on", "year"):
        if hasattr(model, name):
            columns.append(getattr(model, name).desc().nulls_first())
    columns.append(model.created_at)
    return columns


async def list_items(
    session: AsyncSession, profile: ProfessionalProfile, section: Section
) -> list[Any]:
    model: Any = section.model
    stmt = select(model).where(model.profile_id == profile.id).order_by(*_order_columns(section))
    return list((await session.execute(stmt)).scalars())


async def get_item(
    session: AsyncSession, profile: ProfessionalProfile, section: Section, item_id: uuid.UUID
) -> Any:
    model: Any = section.model
    item = (
        await session.execute(
            select(model).where(model.id == item_id, model.profile_id == profile.id)
        )
    ).scalar_one_or_none()
    if item is None:
        raise NotFoundError(f"{section.label} item not found")
    return item


def _initial_status(source: ItemSource) -> VerificationStatus:
    # What the user types is theirs; anything extracted by software needs their review first.
    return (
        VerificationStatus.VERIFIED
        if source == ItemSource.MANUAL
        else VerificationStatus.UNVERIFIED
    )


def _apply_values(section: Section, item: Any, values: dict[str, Any]) -> None:
    if section.key == "research" and "publication_ids" in values:
        values["publication_ids"] = [str(pid) for pid in values["publication_ids"]]
    if section.key == "skills" and "name" in values:
        name = normalize_skill_name(values["name"])
        values["name"] = name
        values["normalized_key"] = canonical_key(name) or name.lower()
        if values.get("category") is None:
            values["category"] = skill_category(name)
    for key, value in values.items():
        setattr(item, key, value)


async def _ensure_unique_skill(
    session: AsyncSession, profile: ProfessionalProfile, key: str, exclude: uuid.UUID | None = None
) -> None:
    stmt = select(Skill.id).where(Skill.profile_id == profile.id, Skill.normalized_key == key)
    if exclude is not None:
        stmt = stmt.where(Skill.id != exclude)
    if (await session.execute(stmt)).first() is not None:
        raise ConflictError("That skill is already in your profile")


async def create_item(
    session: AsyncSession,
    profile: ProfessionalProfile,
    section: Section,
    data: dict[str, Any],
    *,
    source: ItemSource = ItemSource.MANUAL,
) -> Any:
    status = _initial_status(source)
    model: Any = section.model
    item: Any = model(
        profile_id=profile.id,
        source=source,
        verification_status=status,
        verified_at=utcnow() if status == VerificationStatus.VERIFIED else None,
    )
    _apply_values(section, item, dict(data))
    if section.key == "skills":
        await _ensure_unique_skill(session, profile, item.normalized_key)
    if section.key == "facts":
        item.origin = FactOrigin.USER
        item.source_entity = "user"
        item.content_hash = fact_sync.fact_hash("user", "fact", item.fact)
    session.add(item)
    await session.flush()
    if section.derives_facts:
        await fact_sync.sync_derived_facts(session, profile.id, section.entity, item)
    bump_version(profile)
    return item


async def update_item(
    session: AsyncSession,
    profile: ProfessionalProfile,
    section: Section,
    item_id: uuid.UUID,
    data: dict[str, Any],
) -> Any:
    item = await get_item(session, profile, section, item_id)
    if section.key == "facts" and item.origin == FactOrigin.DERIVED:
        raise ValidationFailedError(
            "Derived facts are generated from your profile items; edit the source item instead."
        )
    _apply_values(section, item, dict(data))
    if section.key == "skills":
        await _ensure_unique_skill(session, profile, item.normalized_key, exclude=item.id)
    if section.key == "facts":
        item.content_hash = fact_sync.fact_hash("user", "fact", item.fact)
    await session.flush()
    if section.derives_facts:
        await fact_sync.sync_derived_facts(session, profile.id, section.entity, item)
    bump_version(profile)
    return item


async def delete_item(
    session: AsyncSession, profile: ProfessionalProfile, section: Section, item_id: uuid.UUID
) -> None:
    item = await get_item(session, profile, section, item_id)
    if section.key == "facts" and item.origin == FactOrigin.DERIVED:
        raise ValidationFailedError(
            "Derived facts cannot be deleted; reject the fact or edit its source item."
        )
    if section.derives_facts:
        await fact_sync.delete_derived_facts(session, profile.id, section.entity, [item.id])
    await session.delete(item)
    bump_version(profile)


async def set_status(
    session: AsyncSession,
    profile: ProfessionalProfile,
    section: Section,
    item_ids: list[uuid.UUID],
    status: VerificationStatus,
) -> list[Any]:
    items = [await get_item(session, profile, section, item_id) for item_id in item_ids]
    now = utcnow()
    for item in items:
        item.verification_status = status
        item.verified_at = now if status == VerificationStatus.VERIFIED else None
        if section.derives_facts:
            await fact_sync.sync_derived_facts(session, profile.id, section.entity, item)
    bump_version(profile)
    return items


async def update_basics(
    session: AsyncSession, profile: ProfessionalProfile, data: ProfileBasicsIn
) -> ProfessionalProfile:
    values = data.model_dump(exclude_unset=True)
    if "other_links" in values and values["other_links"] is not None:
        values["other_links"] = [dict(link) for link in values["other_links"]]
    for key, value in values.items():
        if key in {"other_links", "authorized_countries"} and value is None:
            value = []
        setattr(profile, key, value)
    if {"summary", "headline", "current_role"} & values.keys():
        # The user wrote or reviewed these just now.
        profile.basics_status = VerificationStatus.VERIFIED
    bump_version(profile)
    await session.flush()
    return profile


async def update_preferences(
    session: AsyncSession, profile: ProfessionalProfile, data: PreferencesIn
) -> CareerPreferences:
    prefs = await get_preferences(session, profile)
    list_fields = {
        "target_roles", "target_industries", "target_technologies", "target_companies",
        "excluded_companies", "excluded_keywords", "target_countries", "target_cities",
        "sponsorship_required_countries",
        "employment_types", "seniority_levels",
    }  # fmt: skip
    for key, value in data.model_dump(exclude_unset=True).items():
        if key in list_fields:
            value = [str(v) for v in (value or [])]
        if key in {"include_research", "entry_level_only", "hide_unsuitable"} and value is None:
            continue
        setattr(prefs, key, value)
    bump_version(profile)
    await session.flush()
    return prefs


def compute_stats(snapshot: ProfileSnapshot) -> ProfileStats:
    profile, prefs = snapshot.profile, snapshot.preferences
    items = snapshot.items()
    user_facts = [f for f in snapshot.facts if f.origin == FactOrigin.USER]
    counted = [*items, *user_facts]
    verified = sum(1 for i in counted if i.verification_status == VerificationStatus.VERIFIED)
    unverified = sum(1 for i in counted if i.verification_status == VerificationStatus.UNVERIFIED)
    outdated = sum(1 for i in counted if i.verification_status == VerificationStatus.OUTDATED)

    checks: list[tuple[str, str, bool, int]] = [
        ("basics", "Add your name, email and location",
         bool(profile.full_name and profile.contact_email and profile.location), 10),
        ("summary", "Write a short professional summary", bool(profile.summary), 10),
        ("education", "Add your education", bool(snapshot.education), 15),
        ("experience", "Add experience, projects or research",
         bool(snapshot.experience or snapshot.projects or snapshot.research), 25),
        ("skills", "List at least five skills", len(snapshot.skills) >= 5, 15),
        ("preferences", "Choose target roles and locations",
         bool(prefs.target_roles) and bool(prefs.target_countries or prefs.target_cities
                                           or prefs.remote_preference.value == "REMOTE"), 15),
        ("authorization", "Describe your work authorization",
         bool(profile.work_authorization)
         or profile.sponsorship_requirement != SponsorshipRequirement.UNKNOWN, 5),
        ("verified", "Review and verify imported items", bool(counted) and unverified == 0, 5),
    ]  # fmt: skip
    total = sum(weight for *_, weight in checks)
    done = sum(weight for *_, ok, weight in checks if ok)
    return ProfileStats(
        completeness=round(100 * done / total),
        verified_items=verified,
        unverified_items=unverified,
        outdated_items=outdated,
        checklist=[ChecklistItem(key=k, label=label, done=ok) for k, label, ok, _ in checks],
    )
