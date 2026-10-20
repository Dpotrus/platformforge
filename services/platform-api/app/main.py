import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.v1.applications import router as applications_router
from app.db.session import dispose_database_resources
from app.exceptions import (
    ApplicationStorageError,
    ApplicationStorageUnavailable,
)

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        dispose_database_resources()

app = FastAPI(
    title="PlatformForge API",
    description="Internal Developer Platform built with Python and FastAPI",
    version="0.1.0",
    lifespan=lifespan,
)

@app.exception_handler(ApplicationStorageUnavailable)
async def handle_storage_unavailable(
        request: Request,
        exc: ApplicationStorageUnavailable,
) -> JSONResponse:
    logger.error(
        "Application storage unavailable",
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return JSONResponse(
        status_code=503,
        content={
            "detail": "Service temporarily unavailable",
        },
    )


@app.exception_handler(ApplicationStorageError)
async def handle_storage_error(
        request: Request,
        exc: ApplicationStorageError,
) -> JSONResponse:
    logger.error(
        "Application storage operation failed",
        exc_info=(type(exc), exc, exc.__traceback__),
    )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Database operation failed",
        },
    )

app.include_router(applications_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "platformforge-api",
    }
