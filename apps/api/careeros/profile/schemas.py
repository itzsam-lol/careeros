"""Profile API schemas (input validation and response shapes)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)

from careeros.core.enums import CompensationPeriod, EmploymentType, RemotePreference
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


def _validate_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        raise ValueError("must be an http(s) URL")
    return value


ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=8000)]
ListItem = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]
TextList = Annotated[list[ListItem], Field(max_length=40)]
Url = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=500), AfterValidator(_validate_url)
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _DateRangeMixin(_Strict):
    @model_validator(mode="after")
    def _check_dates(self) -> Any:
        start = getattr(self, "start_date", None)
        end = getattr(self, "end_date", None)
        if start and end and end < start:
            raise ValueError("end_date must be on or after start_date")
        return self


class Link(_Strict):
    label: ShortText
    url: Url


# --- Basics & preferences ------------------------------------------------------------------


class ProfileBasicsIn(_Strict):
    full_name: ShortText | None = None
    headline: ShortText | None = None
    current_role: ShortText | None = None
    summary: LongText | None = None
    location: ShortText | None = None
    phone: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    contact_email: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None
    ) = None
    linkedin_url: Url | None = None
    github_url: Url | None = None
    portfolio_url: Url | None = None
    other_links: Annotated[list[Link], Field(max_length=10)] | None = None
    work_authorization: LongText | None = None
    authorized_countries: Annotated[list[ShortText], Field(max_length=30)] | None = None
    sponsorship_requirement: SponsorshipRequirement | None = None
    availability: LongText | None = None
    earliest_start_date: date | None = None


class ProfileBasicsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    full_name: str | None
    headline: str | None
    current_role: str | None
    summary: str | None
    location: str | None
    phone: str | None
    contact_email: str | None
    linkedin_url: str | None
    github_url: str | None
    portfolio_url: str | None
    other_links: list[dict[str, Any]]
    work_authorization: str | None
    authorized_countries: list[str]
    sponsorship_requirement: SponsorshipRequirement
    availability: str | None
    earliest_start_date: date | None
    basics_status: VerificationStatus
    version: int
    updated_at: datetime


class PreferencesIn(_Strict):
    target_roles: Annotated[list[ShortText], Field(max_length=25)] | None = None
    target_industries: Annotated[list[ShortText], Field(max_length=25)] | None = None
    target_technologies: Annotated[list[ShortText], Field(max_length=50)] | None = None
    target_companies: Annotated[list[ShortText], Field(max_length=100)] | None = None
    excluded_companies: Annotated[list[ShortText], Field(max_length=100)] | None = None
    excluded_keywords: Annotated[list[ShortText], Field(max_length=50)] | None = None
    target_countries: Annotated[list[ShortText], Field(max_length=30)] | None = None
    target_cities: Annotated[list[ShortText], Field(max_length=50)] | None = None
    remote_preference: RemotePreference | None = None
    employment_types: list[EmploymentType] | None = None
    seniority_levels: Annotated[list[ShortText], Field(max_length=10)] | None = None
    include_research: bool | None = None
    min_compensation: Annotated[int, Field(ge=0, le=100_000_000)] | None = None
    compensation_currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")] | None = None
    compensation_period: CompensationPeriod | None = None
    notes: LongText | None = None


class PreferencesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_roles: list[str]
    target_industries: list[str]
    target_technologies: list[str]
    target_companies: list[str]
    excluded_companies: list[str]
    excluded_keywords: list[str]
    target_countries: list[str]
    target_cities: list[str]
    remote_preference: RemotePreference
    employment_types: list[str]
    seniority_levels: list[str]
    include_research: bool
    min_compensation: int | None
    compensation_currency: str | None
    compensation_period: CompensationPeriod | None
    notes: str | None


# --- Items ------------------------------------------------------------------------------------


class ItemMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    verification_status: VerificationStatus
    verified_at: datetime | None
    source: ItemSource
    sort_order: int
    created_at: datetime
    updated_at: datetime


class EducationIn(_DateRangeMixin):
    institution: ShortText
    degree: ShortText
    field: ShortText | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    gpa: Annotated[str, StringConstraints(strip_whitespace=True, max_length=40)] | None = None
    location: ShortText | None = None
    description: LongText | None = None
    coursework: TextList = Field(default_factory=list)
    honors: TextList = Field(default_factory=list)
    sort_order: int = 0


class EducationOut(ItemMeta):
    institution: str
    degree: str
    field: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    gpa: str | None
    location: str | None
    description: str | None
    coursework: list[str]
    honors: list[str]


class ExperienceIn(_DateRangeMixin):
    organization: ShortText
    role: ShortText
    employment_type: EmploymentType | None = None
    location: ShortText | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    description: LongText | None = None
    achievements: TextList = Field(default_factory=list)
    technologies: Annotated[list[ShortText], Field(max_length=60)] = Field(default_factory=list)
    url: Url | None = None
    sort_order: int = 0


class ExperienceOut(ItemMeta):
    organization: str
    role: str
    employment_type: EmploymentType | None
    location: str | None
    start_date: date | None
    end_date: date | None
    is_current: bool
    description: str | None
    achievements: list[str]
    technologies: list[str]
    url: str | None


class ProjectIn(_DateRangeMixin):
    name: ShortText
    role: ShortText | None = None
    description: LongText | None = None
    technologies: Annotated[list[ShortText], Field(max_length=60)] = Field(default_factory=list)
    highlights: TextList = Field(default_factory=list)
    impact: LongText | None = None
    metrics: TextList = Field(default_factory=list)
    url: Url | None = None
    repository_url: Url | None = None
    start_date: date | None = None
    end_date: date | None = None
    sort_order: int = 0


class ProjectOut(ItemMeta):
    name: str
    role: str | None
    description: str | None
    technologies: list[str]
    highlights: list[str]
    impact: str | None
    metrics: list[str]
    url: str | None
    repository_url: str | None
    start_date: date | None
    end_date: date | None


class ResearchIn(_DateRangeMixin):
    organization: ShortText
    title: MediumText
    supervisor: ShortText | None = None
    description: LongText | None = None
    methods: TextList = Field(default_factory=list)
    technologies: Annotated[list[ShortText], Field(max_length=60)] = Field(default_factory=list)
    outcomes: TextList = Field(default_factory=list)
    publication_ids: Annotated[list[uuid.UUID], Field(max_length=30)] = Field(default_factory=list)
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    url: Url | None = None
    sort_order: int = 0


class ResearchOut(ItemMeta):
    organization: str
    title: str
    supervisor: str | None
    description: str | None
    methods: list[str]
    technologies: list[str]
    outcomes: list[str]
    publication_ids: list[str]
    start_date: date | None
    end_date: date | None
    is_current: bool
    url: str | None


class PublicationIn(_Strict):
    title: MediumText
    venue: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    status: PublicationStatus = PublicationStatus.PUBLISHED
    url: Url | None = None
    year: Annotated[int, Field(ge=1950, le=2100)] | None = None
    authors: Annotated[list[ShortText], Field(max_length=100)] = Field(default_factory=list)
    summary: LongText | None = None
    sort_order: int = 0


class PublicationOut(ItemMeta):
    title: str
    venue: str | None
    status: PublicationStatus
    url: str | None
    year: int | None
    authors: list[str]
    summary: str | None


class SkillIn(_Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    category: SkillCategory | None = None
    proficiency: SkillProficiency | None = None
    years_experience: Annotated[float, Field(ge=0, le=60)] | None = None
    sort_order: int = 0


class SkillOut(ItemMeta):
    name: str
    normalized_key: str
    category: SkillCategory
    proficiency: SkillProficiency | None
    years_experience: float | None


class AchievementIn(_Strict):
    kind: AchievementKind = AchievementKind.AWARD
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    organization: ShortText | None = None
    achieved_on: date | None = None
    description: LongText | None = None
    url: Url | None = None
    sort_order: int = 0


class AchievementOut(ItemMeta):
    kind: AchievementKind
    title: str
    organization: str | None
    achieved_on: date | None
    description: str | None
    url: str | None


class CareerFactIn(_Strict):
    category: FactCategory = FactCategory.GENERAL
    fact: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)]
    context: Annotated[str, StringConstraints(strip_whitespace=True, max_length=300)] | None = None
    confidence: Annotated[float, Field(ge=0, le=1)] = 1.0
    valid_from: date | None = None
    valid_until: date | None = None
    sort_order: int = 0


class CareerFactOut(ItemMeta):
    category: FactCategory
    fact: str
    context: str | None
    source_entity: str | None
    source_id: uuid.UUID | None
    source_field: str | None
    origin: FactOrigin
    confidence: float
    valid_from: date | None
    valid_until: date | None


class ReusableAnswerIn(_Strict):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=3, max_length=1000)
    ]
    answer: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)]
    category: AnswerCategory = AnswerCategory.OTHER
    tags: Annotated[list[ShortText], Field(max_length=20)] = Field(default_factory=list)
    sort_order: int = 0


class ReusableAnswerOut(ItemMeta):
    question: str
    answer: str
    category: AnswerCategory
    tags: list[str]


class VerificationUpdate(_Strict):
    status: VerificationStatus


class BulkVerificationRequest(_Strict):
    section: str
    ids: Annotated[list[uuid.UUID], Field(min_length=1, max_length=200)]
    status: VerificationStatus


# --- Aggregates -------------------------------------------------------------------------------


class ChecklistItem(BaseModel):
    key: str
    label: str
    done: bool


class ProfileStats(BaseModel):
    completeness: int = Field(description="0-100")
    verified_items: int
    unverified_items: int
    outdated_items: int
    checklist: list[ChecklistItem]


class ProfileOut(BaseModel):
    basics: ProfileBasicsOut
    preferences: PreferencesOut
    education: list[EducationOut]
    experience: list[ExperienceOut]
    projects: list[ProjectOut]
    research: list[ResearchOut]
    publications: list[PublicationOut]
    skills: list[SkillOut]
    achievements: list[AchievementOut]
    facts: list[CareerFactOut]
    answers: list[ReusableAnswerOut]
    stats: ProfileStats
