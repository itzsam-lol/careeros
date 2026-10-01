"""Imports every model module so `Base.metadata` is complete (Alembic, tests, tooling)."""

from __future__ import annotations

from careeros.audit import models as audit_models
from careeros.companies import models as company_models
from careeros.db.base import Base
from careeros.discovery import models as discovery_models
from careeros.events import models as event_models
from careeros.evidence import models as evidence_models
from careeros.intelligence import models as intelligence_models
from careeros.jobs import models as job_models
from careeros.llm import models as llm_models
from careeros.matching import models as matching_models
from careeros.notifications import models as notification_models
from careeros.outreach import models as outreach_models
from careeros.profile import models as profile_models
from careeros.resumes import models as resume_models
from careeros.tasks import models as task_models
from careeros.users import models as user_models

metadata = Base.metadata

__all__ = [
    "audit_models",
    "company_models",
    "discovery_models",
    "event_models",
    "evidence_models",
    "intelligence_models",
    "job_models",
    "llm_models",
    "matching_models",
    "metadata",
    "notification_models",
    "outreach_models",
    "profile_models",
    "resume_models",
    "task_models",
    "user_models",
]
