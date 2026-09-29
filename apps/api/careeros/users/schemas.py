from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MatchingSettings(BaseModel):
    high_match_threshold: float = Field(0.75, ge=0, le=1)
    notify_threshold: float = Field(0.55, ge=0, le=1)


class OutreachLimits(BaseModel):
    """Conservative defaults that protect the user from accidental spam (spec §87)."""

    max_emails_per_day: int = Field(5, ge=0, le=50)
    max_emails_per_company_per_day: int = Field(1, ge=0, le=10)
    max_follow_ups_per_contact: int = Field(1, ge=0, le=3)
    follow_up_after_days: int = Field(5, ge=1, le=60)
    contact_cooldown_days: int = Field(7, ge=0, le=90)


class ResumeSettings(BaseModel):
    template: str = "classic"
    include_unverified: bool = False
    max_pages: int = Field(1, ge=1, le=3)


class NotificationSettings(BaseModel):
    notify_new_jobs: bool = True
    deadline_warning_hours: int = Field(72, ge=1, le=24 * 30)


class UserSettings(BaseModel):
    timezone: str = "UTC"
    matching: MatchingSettings = Field(default_factory=MatchingSettings)
    outreach: OutreachLimits = Field(default_factory=OutreachLimits)
    resume: ResumeSettings = Field(default_factory=ResumeSettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


def merge_settings(current: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge a partial settings document into the stored one."""
    merged = dict(current)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = merge_settings(merged[key], value)
        else:
            merged[key] = value
    return merged


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str | None
    auth_provider: str
    created_at: datetime
    settings: UserSettings
    has_profile: bool = False
