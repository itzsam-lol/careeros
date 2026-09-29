"""Registers every task handler and event subscriber (imported once per process)."""

from __future__ import annotations

from careeros import orchestrator
from careeros.discovery import tasks as discovery_tasks

__all__ = ["discovery_tasks", "orchestrator"]
