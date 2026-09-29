"""Imports every model module so `Base.metadata` is complete (Alembic, tests, tooling)."""

from __future__ import annotations

from careeros.audit import models as audit_models
from careeros.db.base import Base
from careeros.evidence import models as evidence_models
from careeros.llm import models as llm_models
from careeros.profile import models as profile_models
from careeros.users import models as user_models

metadata = Base.metadata

__all__ = [
    "audit_models",
    "evidence_models",
    "llm_models",
    "metadata",
    "profile_models",
    "user_models",
]
