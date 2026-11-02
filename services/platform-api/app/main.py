from app.config import get_settings
from app.observability.tracing import (
    acquire_sqlalchemy_ownership,
    create_tracer_provider,
    instrument_fastapi,
    instrument_sqlalchemy,
    release_sqlalchemy_ownership,
    uninstrument_sqlalchemy,
)

from app.observability.logging import configure_logging
from app.observability.request_logging import RequestLoggingMiddleware
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from opentelemetry.sdk.trace import TracerProvider

from app.api.v1.applications import router as applications_router
from app.db.session import (
    dispose_database_resources,
    get_database_resources,
    get_database_url,
)
from app.exceptions import (
    ApplicationStorageError,
    ApplicationStorageUnavailable,
)
from app.observability.middleware import PrometheusMetricsMiddleware

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    tracer_provider: TracerProvider | None = getattr(app.state, "tracer_provider", None)
    owner: object | None = None
    sqlalchemy_instrumented = False
    errors: list[BaseException] = []

    try:
        owner = acquire_sqlalchemy_ownership()

        if tracer_provider is not None:
            database_url = get_database_url()
            engine, _ = get_database_resources(database_url)
            instrument_sqlalchemy(owner, engine, tracer_provider)
            sqlalchemy_instrumented = True

        yield
    except BaseException as exc:
        errors.append(exc)
    finally:
        try:
            if owner is not None:
                dispose_database_resources()
        except BaseException as exc:
            errors.append(exc)
        finally:
            try:
                if sqlalchemy_instrumented:
                    uninstrument_sqlalchemy(owner)
            except BaseException as exc:
                errors.append(exc)
            finally:
                try:
                    if tracer_provider is not None:
                        tracer_provider.shutdown()
                except BaseException as exc:
                    errors.append(exc)
                finally:
                    try:
                        if owner is not None:
                            release_sqlalchemy_ownership(owner)
                    except BaseException as exc:
                        errors.append(exc)

    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup("Application lifecycle failed", errors)


def create_app() -> FastAPI:
    settings = get_settings()

    configure_logging(
        level=settings.log_level,
        log_format=settings.log_format,
        service_name=settings.otel_service_name,
    )

    application = FastAPI(
        title="PlatformForge API",
        description="Internal Developer Platform built with Python and FastAPI",
        version="0.1.0",
        lifespan=lifespan,
    )

    application.add_middleware(PrometheusMetricsMiddleware)
    application.add_middleware(RequestLoggingMiddleware)

    if settings.otel_tracing_enabled:
        tracer_provider = create_tracer_provider(
            service_name=settings.otel_service_name,
            endpoint=settings.otel_exporter_otlp_endpoint,
        )

        application.state.tracer_provider = tracer_provider

        instrument_fastapi(
            app=application,
            provider=tracer_provider,
        )
    else:
        application.state.tracer_provider = None

    @application.exception_handler(ApplicationStorageUnavailable)
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

    @application.exception_handler(ApplicationStorageError)
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

    application.include_router(
        applications_router,
        prefix="/api/v1",
    )

    @application.get("/health")
    def health_check() -> dict[str, str]:
        return {
            "status": "healthy",
            "service": "platformforge-api",
        }

    @application.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )

    return application


app = create_app()
