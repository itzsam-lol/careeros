"""Profile persistence model (spec §5).

Each profile item carries a verification status, the source it came from and an ordering key.
Items are queried explicitly by `profile_id` (no implicit relationship loading under asyncio).
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import Float, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from careeros.core.enums import CompensationPeriod, EmploymentType, RemotePreference
from careeros.db.base import Base, Timestamped, UUIDPrimaryKey, enum_type
from careeros.intelligence.skills import SkillCategory
from careeros.profile.enums import (
    AchievementKind,
    AnswerCategory,
    FactCategory,
    FactOrigin,
    ItemSource,
    PublicationStatus,
    SkillProficiency,
    SponsorshipRequirement,
    VerificationStatus,
)

_EMPTY_LIST = text("'[]'::jsonb")


class ProfessionalProfile(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "professional_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True
    )
    full_name: Mapped[str | None] = mapped_column(String(200))
    headline: Mapped[str | None] = mapped_column(String(200))
    current_role: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    contact_email: Mapped[str | None] = mapped_column(String(320))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))
    github_url: Mapped[str | None] = mapped_column(String(500))
    portfolio_url: Mapped[str | None] = mapped_column(String(500))
    other_links: Mapped[list[dict[str, Any]]] = mapped_column(
        default=list, server_default=_EMPTY_LIST
    )
    work_authorization: Mapped[str | None] = mapped_column(Text)
    authorized_countries: Mapped[list[str]] = mapped_column(
        default=list, server_default=_EMPTY_LIST
    )
    sponsorship_requirement: Mapped[SponsorshipRequirement] = mapped_column(
        enum_type(SponsorshipRequirement), default=SponsorshipRequirement.UNKNOWN
    )
    availability: Mapped[str | None] = mapped_column(Text)
    earliest_start_date: Mapped[date | None]
    # Trust level of the free-text basics (summary/headline) — imported text starts unverified.
    basics_status: Mapped[VerificationStatus] = mapped_column(
        enum_type(VerificationStatus), default=VerificationStatus.VERIFIED
    )
    # Incremented on every profile change; matches/resumes record the version they used.
    version: Mapped[int] = mapped_column(default=1, server_default="1")
    indexed_version: Mapped[int] = mapped_column(default=0, server_default="0")


class CareerPreferences(UUIDPrimaryKey, Timestamped, Base):
    __tablename__ = "career_preferences"

    profile_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("professional_profiles.id", ondelete="CASCADE"), unique=True
    )
    target_roles: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    target_industries: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    target_technologies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    target_companies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    excluded_companies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    excluded_keywords: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    target_countries: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    target_cities: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    remote_preference: Mapped[RemotePreference] = mapped_column(
        enum_type(RemotePreference), default=RemotePreference.ANY
    )
    employment_types: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    seniority_levels: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    include_research: Mapped[bool] = mapped_column(default=True, server_default="true")
    min_compensation: Mapped[int | None]
    compensation_currency: Mapped[str | None] = mapped_column(String(3))
    compensation_period: Mapped[CompensationPeriod | None] = mapped_column(
        enum_type(CompensationPeriod)
    )
    notes: Mapped[str | None] = mapped_column(Text)


class ProfileItem(UUIDPrimaryKey, Timestamped):
    """Columns shared by every verifiable profile item."""

    @declared_attr
    def profile_id(cls) -> Mapped[uuid.UUID]:  # noqa: N805 - declared_attr convention
        return mapped_column(ForeignKey("professional_profiles.id", ondelete="CASCADE"), index=True)

    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_type(VerificationStatus), default=VerificationStatus.UNVERIFIED
    )
    verified_at: Mapped[datetime | None]
    source: Mapped[ItemSource] = mapped_column(enum_type(ItemSource), default=ItemSource.MANUAL)
    sort_order: Mapped[int] = mapped_column(default=0, server_default="0")


class Education(ProfileItem, Base):
    __tablename__ = "education"

    institution: Mapped[str] = mapped_column(String(200))
    degree: Mapped[str] = mapped_column(String(200))
    field: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    gpa: Mapped[str | None] = mapped_column(String(40))
    location: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    coursework: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    honors: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)


class Experience(ProfileItem, Base):
    __tablename__ = "experiences"

    organization: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    employment_type: Mapped[EmploymentType | None] = mapped_column(enum_type(EmploymentType))
    location: Mapped[str | None] = mapped_column(String(200))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    description: Mapped[str | None] = mapped_column(Text)
    achievements: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    technologies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    url: Mapped[str | None] = mapped_column(String(500))


class Project(ProfileItem, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    technologies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    highlights: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    impact: Mapped[str | None] = mapped_column(Text)
    metrics: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    url: Mapped[str | None] = mapped_column(String(500))
    repository_url: Mapped[str | None] = mapped_column(String(500))
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]


class ResearchExperience(ProfileItem, Base):
    __tablename__ = "research_experiences"

    organization: Mapped[str] = mapped_column(String(200))
    title: Mapped[str] = mapped_column(String(300))
    supervisor: Mapped[str | None] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    methods: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    technologies: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    outcomes: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    publication_ids: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    start_date: Mapped[date | None]
    end_date: Mapped[date | None]
    is_current: Mapped[bool] = mapped_column(default=False)
    url: Mapped[str | None] = mapped_column(String(500))


class Publication(ProfileItem, Base):
    __tablename__ = "publications"

    title: Mapped[str] = mapped_column(String(500))
    venue: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[PublicationStatus] = mapped_column(
        enum_type(PublicationStatus), default=PublicationStatus.PUBLISHED
    )
    url: Mapped[str | None] = mapped_column(String(500))
    year: Mapped[int | None]
    authors: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
    summary: Mapped[str | None] = mapped_column(Text)


class Skill(ProfileItem, Base):
    __tablename__ = "skills"
    __table_args__ = (UniqueConstraint("profile_id", "normalized_key"),)

    name: Mapped[str] = mapped_column(String(120))
    normalized_key: Mapped[str] = mapped_column(String(120))
    category: Mapped[SkillCategory] = mapped_column(
        enum_type(SkillCategory), default=SkillCategory.OTHER
    )
    proficiency: Mapped[SkillProficiency | None] = mapped_column(enum_type(SkillProficiency))
    years_experience: Mapped[float | None] = mapped_column(Float)


class Achievement(ProfileItem, Base):
    """Awards, competitions, leadership, teaching, certifications, volunteering."""

    __tablename__ = "achievements"

    kind: Mapped[AchievementKind] = mapped_column(
        enum_type(AchievementKind), default=AchievementKind.AWARD
    )
    title: Mapped[str] = mapped_column(String(300))
    organization: Mapped[str | None] = mapped_column(String(200))
    achieved_on: Mapped[date | None]
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str | None] = mapped_column(String(500))


class CareerFact(ProfileItem, Base):
    """Atomic, citable statements about the user (spec §5 "critical").

    DERIVED facts are generated from structured items and kept in sync (stable ids while the
    underlying text is unchanged); USER facts are written directly by the user.
    """

    __tablename__ = "career_facts"
    __table_args__ = (Index("ix_career_facts_source", "profile_id", "source_entity", "source_id"),)

    category: Mapped[FactCategory] = mapped_column(enum_type(FactCategory))
    fact: Mapped[str] = mapped_column(Text)
    context: Mapped[str | None] = mapped_column(String(300))
    source_entity: Mapped[str | None] = mapped_column(String(40))
    source_id: Mapped[uuid.UUID | None]
    source_field: Mapped[str | None] = mapped_column(String(40))
    origin: Mapped[FactOrigin] = mapped_column(enum_type(FactOrigin), default=FactOrigin.USER)
    content_hash: Mapped[str] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    valid_from: Mapped[date | None]
    valid_until: Mapped[date | None]


class ReusableAnswer(ProfileItem, Base):
    """Verified answers to recurring application questions."""

    __tablename__ = "reusable_answers"

    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    category: Mapped[AnswerCategory] = mapped_column(
        enum_type(AnswerCategory), default=AnswerCategory.OTHER
    )
    tags: Mapped[list[str]] = mapped_column(default=list, server_default=_EMPTY_LIST)
