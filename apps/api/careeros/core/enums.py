"""Enums shared by several domains (profile, jobs, matching)."""

from __future__ import annotations

from enum import StrEnum


class EmploymentType(StrEnum):
    INTERNSHIP = "INTERNSHIP"
    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    FREELANCE = "FREELANCE"
    RESEARCH = "RESEARCH"
    APPRENTICESHIP = "APPRENTICESHIP"
    TEMPORARY = "TEMPORARY"
    OTHER = "OTHER"


class RemoteType(StrEnum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"
    UNKNOWN = "UNKNOWN"


class RemotePreference(StrEnum):
    REMOTE = "REMOTE"
    HYBRID = "HYBRID"
    ONSITE = "ONSITE"
    ANY = "ANY"


class SeniorityLevel(StrEnum):
    INTERN = "INTERN"
    ENTRY = "ENTRY"
    MID = "MID"
    SENIOR = "SENIOR"
    LEAD = "LEAD"
    MANAGER = "MANAGER"
    UNKNOWN = "UNKNOWN"


class CompensationPeriod(StrEnum):
    YEAR = "YEAR"
    MONTH = "MONTH"
    WEEK = "WEEK"
    HOUR = "HOUR"
