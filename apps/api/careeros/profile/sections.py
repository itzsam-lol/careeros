"""Registry of profile sections. Drives generic CRUD in the service and router."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from careeros.profile import schemas
from careeros.profile.models import (
    Achievement,
    CareerFact,
    Education,
    Experience,
    ProfileItem,
    Project,
    Publication,
    ResearchExperience,
    ReusableAnswer,
    Skill,
)


@dataclass(frozen=True, slots=True)
class Section:
    key: str  # URL segment
    entity: str  # entity name used in fact provenance ("project:<id>")
    label: str
    model: type[ProfileItem]
    schema_in: type[BaseModel]
    schema_out: type[BaseModel]
    derives_facts: bool = True


SECTIONS: dict[str, Section] = {
    s.key: s
    for s in (
        Section(
            "education",
            "education",
            "Education",
            Education,
            schemas.EducationIn,
            schemas.EducationOut,
        ),
        Section(
            "experience",
            "experience",
            "Experience",
            Experience,
            schemas.ExperienceIn,
            schemas.ExperienceOut,
        ),
        Section("projects", "project", "Projects", Project, schemas.ProjectIn, schemas.ProjectOut),
        Section(
            "research",
            "research",
            "Research",
            ResearchExperience,
            schemas.ResearchIn,
            schemas.ResearchOut,
        ),
        Section(
            "publications",
            "publication",
            "Publications",
            Publication,
            schemas.PublicationIn,
            schemas.PublicationOut,
        ),
        Section(
            "skills",
            "skill",
            "Skills",
            Skill,
            schemas.SkillIn,
            schemas.SkillOut,
            derives_facts=False,
        ),
        Section(
            "achievements",
            "achievement",
            "Achievements",
            Achievement,
            schemas.AchievementIn,
            schemas.AchievementOut,
        ),
        Section(
            "facts",
            "career_fact",
            "Career facts",
            CareerFact,
            schemas.CareerFactIn,
            schemas.CareerFactOut,
            derives_facts=False,
        ),
        Section(
            "answers",
            "answer",
            "Reusable answers",
            ReusableAnswer,
            schemas.ReusableAnswerIn,
            schemas.ReusableAnswerOut,
            derives_facts=False,
        ),
    )
}

ENTITY_TO_SECTION: dict[str, Section] = {s.entity: s for s in SECTIONS.values()}
