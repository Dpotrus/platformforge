from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.applications import router as applications_router
from app.db.session import dispose_database_resources


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

app.include_router(applications_router, prefix="/api/v1")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "service": "platformforge-api",
    }
