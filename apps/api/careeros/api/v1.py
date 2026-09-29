"""Public API v1. Everything except /auth/config and /auth/login requires a signed-in user."""

from __future__ import annotations

from fastapi import APIRouter

from careeros.auth.router import router as auth_router
from careeros.dashboard.router import router as dashboard_router
from careeros.discovery.router import router as sources_router
from careeros.evidence.router import router as evidence_router
from careeros.jobs.router import router as jobs_router
from careeros.notifications.router import router as notifications_router
from careeros.profile.router import router as profile_router
from careeros.tasks.router import router as activity_router
from careeros.users.router import router as me_router

router = APIRouter()
router.include_router(auth_router)
router.include_router(me_router)
router.include_router(dashboard_router)
router.include_router(profile_router)
router.include_router(evidence_router)
router.include_router(sources_router)
router.include_router(jobs_router)
router.include_router(notifications_router)
router.include_router(activity_router)
