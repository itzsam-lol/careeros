"""Uniform JSON error envelope: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from careeros.core.errors import CareerOSError, RateLimitedError
from careeros.core.logging import get_logger

log = get_logger(__name__)


def _envelope(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(CareerOSError)
    async def _domain_error(_: Request, exc: CareerOSError) -> JSONResponse:
        if exc.http_status >= 500:
            log.error("request_failed", code=exc.code, error=exc.message)
        headers: dict[str, str] = {}
        if isinstance(exc, RateLimitedError):
            headers["Retry-After"] = str(exc.details.get("retry_after_seconds", 60))
        if exc.http_status == 401:
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            _envelope(exc.code, exc.message, exc.details),
            status_code=exc.http_status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": err.get("loc"), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return JSONResponse(
            _envelope("validation_failed", "Invalid request", {"errors": jsonable_encoder(errors)}),
            status_code=422,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(
            _envelope(code, str(exc.detail)), status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error", error_type=type(exc).__name__)
        return JSONResponse(
            _envelope("internal_error", "An unexpected error occurred"), status_code=500
        )
