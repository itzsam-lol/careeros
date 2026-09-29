"""Imports every model module so `Base.metadata` is complete (Alembic, tests, tooling)."""

from __future__ import annotations

from careeros.audit import models as audit_models
from careeros.db.base import Base
from careeros.users import models as user_models

metadata = Base.metadata

__all__ = ["audit_models", "metadata", "user_models"]
