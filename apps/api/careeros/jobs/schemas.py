from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from careeros.core.enums import CompensationPeriod, EmploymentType, RemoteType, SeniorityLevel
from careeros.intelligence.extraction import JobExtraction
from careeros.jobs.models import ApplicationPlatform, ApplicationStage, JobLifecycle


class JobView(StrEnum):
    ALL = "ALL"
    NEW = "NEW"
    HIGH_MATCH = "HIGH_MATCH"
    DEADLINE_SOON = "DEADLINE_SOON"
    SAVED = "SAVED"
    DISMISSED = "DISMISSED"
    CLOSED = "CLOSED"
    APPLIED = "APPLIED"  # anything with an application stage (the tracker)
    READY = "READY"  # dream-company roles with a tailored kit, not applied to yet


class JobSort(StrEnum):
    SCORE = "SCORE"
    RECENT = "RECENT"
    DEADLINE = "DEADLINE"


class Salary(BaseModel):
    minimum: float | None
    maximum: float | None
    currency: str | None
    period: CompensationPeriod | None


class MatchSummary(BaseModel):
    overall_score: float
    eligible: bool
    label: str
    reasoning: str
    dimensions: dict[str, float]
    top_strengths: list[str]
    top_gaps: list[str]
    updated_at: datetime


class JobCard(BaseModel):
    job_id: uuid.UUID
    title: str
    company: str
    company_id: uuid.UUID | None
    location: str | None
    countries: list[str]
    remote_type: RemoteType
    employment_type: EmploymentType | None
    seniority: SeniorityLevel
    posted_at: datetime | None
    deadline: datetime | None
    first_seen_at: datetime
    application_platform: ApplicationPlatform
    application_url: str | None
    is_active: bool
    status: JobLifecycle
    salary: Salary | None
    source_name: str | None
    match: MatchSummary | None
    application_stage: ApplicationStage | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None


class JobList(BaseModel):
    items: list[JobCard]
    total: int


class EligibilityOut(BaseModel):
    key: str
    label: str
    status: str
    detail: str


class MatchDetail(MatchSummary):
    eligibility: list[EligibilityOut]
    strengths: list[dict[str, Any]]
    gaps: list[dict[str, Any]]
    concerns: list[str]
    requirement_coverage: list[dict[str, Any]]
    evidence: list[dict[str, Any]]
    profile_version: int
    scorer: str
    stale: bool


class SourceLinkOut(BaseModel):
    source_type: str
    source_name: str | None
    url: str | None
    active: bool
    first_seen_at: datetime
    last_seen_at: datetime


class CompanyOut(BaseModel):
    id: uuid.UUID
    name: str
    website: str | None
    industry: str | None
    description: str | None


class JobDetail(BaseModel):
    card: JobCard
    description: str
    department: str | None
    canonical_url: str | None
    analysis: JobExtraction | None
    analysis_extractor: str | None
    match: MatchDetail | None
    sources: list[SourceLinkOut]
    company: CompanyOut | None
    note: str | None
    dismiss_reason: str | None


class DismissRequest(BaseModel):
    reason: str | None = Field(None, max_length=200)


class NoteRequest(BaseModel):
    note: str | None = Field(None, max_length=4000)


class ApplicationUpdate(BaseModel):
    stage: ApplicationStage | None = None  # null clears tracking for this job
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    clear_follow_up: bool = False
    note: str | None = Field(None, max_length=5000)


class StageEvent(BaseModel):
    stage: ApplicationStage | None
    at: datetime


class ApplicationOut(BaseModel):
    job_id: uuid.UUID
    stage: ApplicationStage | None
    applied_at: datetime | None
    follow_up_at: datetime | None
    note: str | None
    history: list[StageEvent]
