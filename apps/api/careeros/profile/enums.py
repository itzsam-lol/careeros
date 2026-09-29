from __future__ import annotations

from enum import StrEnum


class VerificationStatus(StrEnum):
    """Trust level of a profile item (spec §6). Only VERIFIED is used by default."""

    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    OUTDATED = "OUTDATED"
    REJECTED = "REJECTED"


class ItemSource(StrEnum):
    MANUAL = "MANUAL"
    RESUME_IMPORT = "RESUME_IMPORT"
    JSON_IMPORT = "JSON_IMPORT"
    AGENT = "AGENT"


class SponsorshipRequirement(StrEnum):
    REQUIRED = "REQUIRED"
    NOT_REQUIRED = "NOT_REQUIRED"
    FUTURE = "FUTURE"  # not now, but will be required later (e.g. after a student visa ends)
    UNKNOWN = "UNKNOWN"


class SkillProficiency(StrEnum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"
    EXPERT = "EXPERT"


class PublicationStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    ACCEPTED = "ACCEPTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    PREPRINT = "PREPRINT"
    IN_PREPARATION = "IN_PREPARATION"


class AchievementKind(StrEnum):
    AWARD = "AWARD"
    COMPETITION = "COMPETITION"
    LEADERSHIP = "LEADERSHIP"
    TEACHING = "TEACHING"
    CERTIFICATION = "CERTIFICATION"
    VOLUNTEERING = "VOLUNTEERING"
    OTHER = "OTHER"


class FactCategory(StrEnum):
    EDUCATION = "EDUCATION"
    EXPERIENCE = "EXPERIENCE"
    PROJECT = "PROJECT"
    RESEARCH = "RESEARCH"
    PUBLICATION = "PUBLICATION"
    ACHIEVEMENT = "ACHIEVEMENT"
    METRIC = "METRIC"
    SKILL = "SKILL"
    GENERAL = "GENERAL"


class FactOrigin(StrEnum):
    DERIVED = "DERIVED"  # generated from a structured profile item, kept in sync automatically
    USER = "USER"  # written directly by the user


class AnswerCategory(StrEnum):
    WORK_AUTHORIZATION = "WORK_AUTHORIZATION"
    SPONSORSHIP = "SPONSORSHIP"
    RELOCATION = "RELOCATION"
    SALARY = "SALARY"
    AVAILABILITY = "AVAILABILITY"
    MOTIVATION = "MOTIVATION"
    EXPERIENCE = "EXPERIENCE"
    DEMOGRAPHIC = "DEMOGRAPHIC"
    OTHER = "OTHER"
