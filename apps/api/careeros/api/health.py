from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from careeros import __version__
from careeros.api.deps import ContainerDep
from careeros.core.logging import get_logger

router = APIRouter(tags=["health"])
log = get_logger(__name__)


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@router.get("/readyz", summary="Readiness probe (checks the database)")
async def readyz(container: ContainerDep) -> JSONResponse:
    try:
        await container.db.ping()
    except Exception as exc:  # readiness must never raise
        log.warning("readiness_failed", error_type=type(exc).__name__)
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return JSONResponse({"status": "ready"})
