"""Structured logging.

Every log line is a structured event. Request/task context (request_id, task_id, job_id, ...)
is carried in contextvars so it is attached automatically. Values under sensitive keys are
redacted before rendering so tokens, cookies and passwords never reach log storage.
"""

from __future__ import annotations

import logging
import re
import sys
from collections.abc import MutableMapping
from typing import Any

import structlog
from structlog.types import EventDict, Processor

# `token(?!s)` redacts access_token/refresh_token but keeps usage counters like input_tokens.
_SENSITIVE_KEY = re.compile(
    r"(password|passwd|secret|token(?!s)|authorization|cookie|api[_-]?key|private[_-]?key|"
    r"credential)",
    re.IGNORECASE,
)
_REDACTED = "[REDACTED]"


def redact_value(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return value
    if isinstance(value, MutableMapping):
        return {
            key: (_REDACTED if _SENSITIVE_KEY.search(str(key)) else redact_value(item, depth + 1))
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return [redact_value(item, depth + 1) for item in value]
    return value


def redact_sensitive(_: Any, __: str, event_dict: EventDict) -> EventDict:
    for key in list(event_dict.keys()):
        if key == "event":
            continue
        if _SENSITIVE_KEY.search(key):
            event_dict[key] = _REDACTED
        else:
            event_dict[key] = redact_value(event_dict[key])
    return event_dict


def add_severity(_: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """Cloud Logging reads the `severity` field from JSON payloads."""
    level = event_dict.get("level", method_name)
    event_dict["severity"] = str(level).upper()
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        redact_sensitive,
    ]
    renderer: Processor
    final: list[Processor]
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
        final = [add_severity, structlog.processors.format_exc_info, renderer]
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())
        final = [renderer]

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *final],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())

    # Route third-party loggers through the same pipeline; our middleware logs requests.
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True
    for noisy in ("httpx", "httpcore", "botocore", "urllib3", "google", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    logger: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(name)
    return logger


bind_context = structlog.contextvars.bind_contextvars
unbind_context = structlog.contextvars.unbind_contextvars
clear_context = structlog.contextvars.clear_contextvars
bound_context = structlog.contextvars.bound_contextvars
