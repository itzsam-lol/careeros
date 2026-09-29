"""Structured profile import. Imported items start UNVERIFIED until the user reviews them."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.core.clock import utcnow
from careeros.core.errors import ConflictError
from careeros.profile import schemas, service
from careeros.profile.enums import ItemSource, VerificationStatus
from careeros.profile.models import ProfessionalProfile
from careeros.profile.sections import SECTIONS


class ProfileImport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    basics: schemas.ProfileBasicsIn | None = None
    preferences: schemas.PreferencesIn | None = None
    education: list[schemas.EducationIn] = Field(default_factory=list, max_length=20)
    experience: list[schemas.ExperienceIn] = Field(default_factory=list, max_length=40)
    projects: list[schemas.ProjectIn] = Field(default_factory=list, max_length=60)
    research: list[schemas.ResearchIn] = Field(default_factory=list, max_length=30)
    publications: list[schemas.PublicationIn] = Field(default_factory=list, max_length=60)
    skills: list[schemas.SkillIn] = Field(default_factory=list, max_length=200)
    achievements: list[schemas.AchievementIn] = Field(default_factory=list, max_length=60)
    facts: list[schemas.CareerFactIn] = Field(default_factory=list, max_length=200)
    answers: list[schemas.ReusableAnswerIn] = Field(default_factory=list, max_length=100)


class ImportResult(BaseModel):
    created: dict[str, int]
    skipped: dict[str, int]
    unverified: int


async def import_profile(
    session: AsyncSession,
    profile: ProfessionalProfile,
    payload: ProfileImport,
    *,
    source: ItemSource = ItemSource.JSON_IMPORT,
    status_override: Literal["VERIFIED"] | None = None,
) -> ImportResult:
    """Add everything in `payload` to the profile (merge semantics; duplicate skills skipped).

    `status_override="VERIFIED"` exists only for developer seeding of synthetic data.
    """
    created: dict[str, int] = {}
    skipped: dict[str, int] = {}
    unverified = 0

    if payload.basics is not None:
        await service.update_basics(session, profile, payload.basics)
        if status_override is None:
            profile.basics_status = VerificationStatus.UNVERIFIED
    if payload.preferences is not None:
        await service.update_preferences(session, profile, payload.preferences)

    for key, section in SECTIONS.items():
        entries: list[BaseModel] = getattr(payload, key)
        for entry in entries:
            try:
                async with session.begin_nested():
                    item = await service.create_item(
                        session, profile, section, entry.model_dump(), source=source
                    )
            except ConflictError:
                skipped[key] = skipped.get(key, 0) + 1
                continue
            if status_override == "VERIFIED":
                await service.set_status(
                    session, profile, section, [item.id], VerificationStatus.VERIFIED
                )
            elif item.verification_status == VerificationStatus.UNVERIFIED:
                unverified += 1
            created[key] = created.get(key, 0) + 1

    profile.updated_at = utcnow()
    await session.flush()
    return ImportResult(created=created, skipped=skipped, unverified=unverified)
