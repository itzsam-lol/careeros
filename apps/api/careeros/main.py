"""FastAPI application factory.

Run locally with:  uvicorn careeros.main:create_app --factory --reload
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from careeros import __version__
from careeros.api.errors import register_exception_handlers
from careeros.api.health import router as health_router
from careeros.api.middleware import RequestContextMiddleware, SecurityHeadersMiddleware
from careeros.api.v1 import router as v1_router
from careeros.config import Settings, get_settings
from careeros.container import Container, build_container
from careeros.core.logging import configure_logging, get_logger

log = get_logger(__name__)


def create_app(settings: Settings | None = None, container: Container | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level, settings.use_json_logs)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        owned = container is None
        active = container or build_container(settings)
        app.state.container = active
        log.info("api_started", env=settings.app_env.value, version=__version__)
        try:
            yield
        finally:
            if owned:
                await active.aclose()

    expose_docs = not settings.is_deployed
    app = FastAPI(
        title="CareerOS API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url=None,
        openapi_url="/openapi.json" if expose_docs else None,
    )
    if container is not None:
        app.state.container = container

    # Middleware added last runs first: request context wraps everything.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=False,  # bearer tokens, no cookies => no CSRF surface
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
        max_age=600,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_deployed)
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(v1_router, prefix="/api/v1")
    return app
