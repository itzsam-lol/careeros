"""Registers every task handler, event subscriber and periodic job (imported once per process)."""

from __future__ import annotations

from careeros import orchestrator
from careeros.discovery import tasks as discovery_tasks
from careeros.intelligence import tasks as intelligence_tasks
from careeros.matching import tasks as matching_tasks
from careeros.resumes import tasks as resume_tasks

__all__ = [
    "discovery_tasks",
    "intelligence_tasks",
    "matching_tasks",
    "orchestrator",
    "resume_tasks",
]
