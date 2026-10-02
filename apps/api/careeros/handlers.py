"""Registers every task handler, event subscriber and periodic job (imported once per process)."""

from __future__ import annotations

from careeros import orchestrator
from careeros.discovery import tasks as discovery_tasks
from careeros.intelligence import tasks as intelligence_tasks
from careeros.matching import tasks as matching_tasks
from careeros.notifications import push as push_tasks
from careeros.outreach import tasks as outreach_tasks
from careeros.resumes import prepare as prepare_tasks
from careeros.resumes import tasks as resume_tasks

__all__ = [
    "discovery_tasks",
    "intelligence_tasks",
    "matching_tasks",
    "orchestrator",
    "outreach_tasks",
    "prepare_tasks",
    "push_tasks",
    "resume_tasks",
]
