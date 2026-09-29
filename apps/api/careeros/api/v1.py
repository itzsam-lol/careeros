"""Public API v1: every router here requires an authenticated user."""

from __future__ import annotations

from fastapi import APIRouter

from careeros.evidence.router import router as evidence_router
from careeros.profile.router import router as profile_router
from careeros.users.router import router as me_router

router = APIRouter()
router.include_router(me_router)
router.include_router(profile_router)
router.include_router(evidence_router)
