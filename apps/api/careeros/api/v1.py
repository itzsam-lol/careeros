"""Public API v1: every router here requires an authenticated user."""

from __future__ import annotations

from fastapi import APIRouter

from careeros.users.router import router as me_router

router = APIRouter()
router.include_router(me_router)
