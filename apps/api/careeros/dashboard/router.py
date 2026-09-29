from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from careeros.api.deps import CurrentUser, DbSession
from careeros.dashboard.counters import collect
from careeros.discovery.models import JobSource
from careeros.events.service import recent_for_user
from careeros.jobs import service as jobs
from careeros.jobs.schemas import JobCard, JobSort, JobView
from careeros.notifications import service as notifications
from careeros.notifications.router import NotificationOut
from careeros.profile.service import compute_stats, get_or_create_profile, load_snapshot
from careeros.tasks.router import EventOut
from careeros.users.service import read_settings

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


class SourceHealth(BaseModel):
    total: int
    enabled: int
    failing: int


class ProfileHealth(BaseModel):
    completeness: int
    unverified_items: int


class DashboardOut(BaseModel):
    counts: dict[str, int]
    top_matches: list[JobCard]
    upcoming_deadlines: list[JobCard]
    notifications: list[NotificationOut]
    recent_activity: list[EventOut]
    sources: SourceHealth
    profile: ProfileHealth


@router.get("", response_model=DashboardOut, summary="Live counts and highlights")
async def get_dashboard(user: CurrentUser, session: DbSession) -> DashboardOut:
    settings = read_settings(user)
    high = settings.matching.high_match_threshold
    counts = await jobs.view_counts(session, user.id, high_threshold=high)
    counts["unread_notifications"] = await notifications.unread_count(session, user.id)
    counts.update(await collect(session, user.id))
    top, _ = await jobs.list_jobs(
        session,
        user.id,
        view=JobView.ALL,
        sort=JobSort.SCORE,
        query=None,
        limit=5,
        offset=0,
        high_threshold=high,
    )
    deadlines, _ = await jobs.list_jobs(
        session, user.id, view=JobView.DEADLINE_SOON, sort=JobSort.DEADLINE, query=None, limit=5, offset=0,
        high_threshold=high,
    )  # fmt: skip
    source_rows = (
        await session.execute(
            select(
                func.count(),
                func.count().filter(JobSource.enabled.is_(True)),
                func.count().filter(JobSource.consecutive_failures >= 3),
            ).where(JobSource.user_id == user.id)
        )
    ).one()
    profile = await get_or_create_profile(session, user)
    stats = compute_stats(await load_snapshot(session, profile))
    latest = await notifications.list_notifications(session, user.id, limit=5)
    events = await recent_for_user(session, user.id, limit=8)
    await session.commit()
    return DashboardOut(
        counts=counts,
        top_matches=[card for card in top if card.match is not None],
        upcoming_deadlines=deadlines,
        notifications=[NotificationOut.model_validate(n) for n in latest],
        recent_activity=[EventOut.model_validate(e) for e in events],
        sources=SourceHealth(total=source_rows[0], enabled=source_rows[1], failing=source_rows[2]),
        profile=ProfileHealth(
            completeness=stats.completeness, unverified_items=stats.unverified_items
        ),
    )
