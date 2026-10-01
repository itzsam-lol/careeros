from __future__ import annotations

import uuid
from dataclasses import asdict
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from careeros.api.deps import ContainerDep, CurrentUser, DbSession
from careeros.companies.insights import company_insights
from careeros.companies.models import Company
from careeros.core.errors import NotFoundError
from careeros.discovery.normalize import normalize_company
from careeros.jobs.models import Job, UserJob
from careeros.profile.service import get_or_create_profile, load_snapshot

router = APIRouter(prefix="/jobs", tags=["companies"])


class RoleCountOut(BaseModel):
    label: str
    count: int


class YourMatchOut(BaseModel):
    job_id: uuid.UUID
    title: str
    location: str | None
    score: float
    eligible: bool


class LinkOut(BaseModel):
    label: str
    url: str


class CompanyInsightsOut(BaseModel):
    company_id: uuid.UUID
    name: str
    summary: str | None
    summary_source: str | None
    website: str | None
    open_roles: int
    entry_level_roles: int
    newest_posting: datetime | None
    by_country: list[RoleCountOut]
    by_level: list[RoleCountOut]
    by_function: list[RoleCountOut]
    top_cities: list[RoleCountOut]
    top_skills: list[RoleCountOut]
    sponsorship_roles: int
    your_matches: list[YourMatchOut]
    people_searches: list[LinkOut]
    research_links: list[LinkOut]


@router.get(
    "/{job_id}/company",
    response_model=CompanyInsightsOut,
    summary="What CareerOS knows about the company behind a job, plus people and research links",
)
async def job_company(
    job_id: uuid.UUID, user: CurrentUser, session: DbSession, container: ContainerDep
) -> CompanyInsightsOut:
    owned = (
        await session.execute(
            select(Job)
            .join(UserJob, UserJob.job_id == Job.id)
            .where(Job.id == job_id, UserJob.user_id == user.id)
        )
    ).scalar_one_or_none()
    if owned is None:
        raise NotFoundError("Job not found")
    company = await session.get(Company, owned.company_id) if owned.company_id else None
    if company is None:
        company = (
            await session.execute(
                select(Company).where(Company.normalized_name == normalize_company(owned.company))
            )
        ).scalar_one_or_none()
    if company is None:
        raise NotFoundError("No company record for this job yet")
    snapshot = await load_snapshot(session, await get_or_create_profile(session, user))
    institution = snapshot.education[0].institution if snapshot.education else None
    home = (snapshot.profile.authorized_countries or ["India"])[0]
    insights = await company_insights(
        session,
        user_id=user.id,
        company=company,
        http=container.fetcher,
        institution=institution,
        home_country=home,
    )
    await session.commit()
    return CompanyInsightsOut.model_validate(asdict(insights))
