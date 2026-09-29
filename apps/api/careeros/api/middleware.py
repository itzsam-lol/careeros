"""Pure-ASGI middleware (no BaseHTTPMiddleware: keeps streaming and contextvars intact)."""

from __future__ import annotations

import re
import time
import uuid

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from careeros.core.logging import bind_context, clear_context, get_logger

log = get_logger("careeros.http")
_SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
_QUIET_PATHS = frozenset({"/healthz", "/readyz"})


class RequestContextMiddleware:
    """Assigns a request id, binds it to the log context and logs one line per request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        incoming = dict(scope.get("headers") or []).get(b"x-request-id", b"").decode("latin-1")
        request_id = incoming if _SAFE_REQUEST_ID.match(incoming) else uuid.uuid4().hex
        clear_context()
        bind_context(request_id=request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers") or [])
                headers.append((b"x-request-id", request_id.encode()))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope.get("path", "")
            if path not in _QUIET_PATHS:
                log.info(
                    "http_request",
                    method=scope.get("method"),
                    path=path,
                    status=status_code,
                    duration_ms=round((time.perf_counter() - started) * 1000, 1),
                )
            clear_context()


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, *, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        is_api = str(scope.get("path", "")).startswith(("/api/", "/internal/"))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                existing = {name.lower() for name, _ in headers}
                extra: list[tuple[bytes, bytes]] = [
                    (b"x-content-type-options", b"nosniff"),
                    (b"x-frame-options", b"DENY"),
                    (b"referrer-policy", b"no-referrer"),
                ]
                if is_api:
                    extra.append(
                        (b"content-security-policy", b"default-src 'none'; frame-ancestors 'none'")
                    )
                    if b"cache-control" not in existing:
                        extra.append((b"cache-control", b"no-store"))
                if self.hsts:
                    extra.append(
                        (b"strict-transport-security", b"max-age=63072000; includeSubDomains")
                    )
                headers.extend(h for h in extra if h[0] not in existing)
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
