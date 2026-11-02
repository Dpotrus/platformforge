from threading import Lock

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy.engine import Engine

from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


_sqlalchemy_lock = Lock()
_sqlalchemy_owner: object | None = None
_sqlalchemy_active = False
_sqlalchemy_activation_attempted = False
_sqlalchemy_recovery_required = False


def acquire_sqlalchemy_ownership() -> object:
    """Reserve the process-wide lifecycle, including when tracing is disabled.

    The returned token is compared by identity. Acquisition never waits for
    another lifecycle or an instrumentation operation to finish. External
    SQLAlchemy auto/manual instrumentation must not run alongside these APIs.
    """
    global _sqlalchemy_owner, _sqlalchemy_activation_attempted

    if not _sqlalchemy_lock.acquire(blocking=False):
        raise RuntimeError("SQLAlchemy lifecycle state is busy")

    try:
        if _sqlalchemy_recovery_required:
            raise RuntimeError("SQLAlchemy instrumentation recovery requires a process restart")
        if _sqlalchemy_owner is not None:
            raise RuntimeError("Another application owns the SQLAlchemy lifecycle")
        if SQLAlchemyInstrumentor().is_instrumented_by_opentelemetry:
            raise RuntimeError("External SQLAlchemy instrumentation is already active")

        _sqlalchemy_owner = object()
        _sqlalchemy_activation_attempted = False
        return _sqlalchemy_owner
    finally:
        _sqlalchemy_lock.release()


def instrument_sqlalchemy(
        owner: object,
        engine: Engine,
        provider: TracerProvider,
) -> None:
    """Instrument an existing engine with the exact FastAPI provider.

    Call once during startup, before requests. In 0.66b2 this also patches
    global SQLAlchemy functions. A failed activation may leave partial patches
    while the public active flag is false; public uninstrument() cannot recover
    that state. Such failures permanently block reuse through these APIs until
    process restart. No private cleanup or global TracerProvider is used.
    """
    global _sqlalchemy_active, _sqlalchemy_recovery_required
    global _sqlalchemy_activation_attempted

    with _sqlalchemy_lock:
        if _sqlalchemy_owner is None or owner is not _sqlalchemy_owner:
            raise RuntimeError("SQLAlchemy lifecycle ownership is required")
        if _sqlalchemy_recovery_required:
            raise RuntimeError("SQLAlchemy instrumentation recovery requires a process restart")
        if _sqlalchemy_activation_attempted:
            raise RuntimeError("This lifecycle has already instrumented SQLAlchemy")

        instrumentor = SQLAlchemyInstrumentor()
        if instrumentor.is_instrumented_by_opentelemetry:
            raise RuntimeError("External SQLAlchemy instrumentation is already active")

        _sqlalchemy_activation_attempted = True
        try:
            instrumentor.instrument(
                engine=engine,
                tracer_provider=provider,
                raise_exception_on_conflict=True,
            )
            if not instrumentor.is_instrumented_by_opentelemetry:
                raise RuntimeError("SQLAlchemy instrumentation did not become active")
        except BaseException:
            # The public flag cannot establish whether partial patches exist.
            _sqlalchemy_recovery_required = True
            raise

        _sqlalchemy_active = True


def uninstrument_sqlalchemy(owner: object) -> None:
    """Remove this owner's instrumentation after all database work has stopped.

    Repeated successful cleanup is harmless. Never remove external activation
    or attempt public cleanup after an uncertain activation/teardown failure.
    """
    global _sqlalchemy_active, _sqlalchemy_recovery_required

    with _sqlalchemy_lock:
        if _sqlalchemy_owner is None or owner is not _sqlalchemy_owner:
            raise RuntimeError("SQLAlchemy lifecycle ownership is required")
        if _sqlalchemy_recovery_required:
            raise RuntimeError("SQLAlchemy instrumentation recovery requires a process restart")
        if not _sqlalchemy_active:
            return

        instrumentor = SQLAlchemyInstrumentor()
        try:
            if not instrumentor.is_instrumented_by_opentelemetry:
                raise RuntimeError("SQLAlchemy instrumentation was changed outside its owner")
            instrumentor.uninstrument()
            if instrumentor.is_instrumented_by_opentelemetry:
                raise RuntimeError("SQLAlchemy instrumentation remained active after cleanup")
        except BaseException:
            _sqlalchemy_recovery_required = True
            raise

        _sqlalchemy_active = False


def release_sqlalchemy_ownership(owner: object) -> None:
    """Release a cleaned lifecycle; never uninstrument implicitly.

    Also permits releasing a failed lifecycle's token, but its process remains
    blocked for restart. Repeated release before another acquisition is harmless.
    """
    global _sqlalchemy_owner

    with _sqlalchemy_lock:
        if _sqlalchemy_owner is None:
            return
        if owner is not _sqlalchemy_owner:
            raise RuntimeError("SQLAlchemy lifecycle belongs to another application")
        if _sqlalchemy_active and not _sqlalchemy_recovery_required:
            raise RuntimeError("Release SQLAlchemy instrumentation before ownership")
        _sqlalchemy_owner = None


def create_tracer_provider(
        service_name: str,
        endpoint: str | None = None,
) -> TracerProvider:
    resource = Resource.create(
        {
            "service.name": service_name,
        }
    )

    provider = TracerProvider(resource=resource)

    if endpoint is not None:
        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
            timeout=5,
        )

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

    return provider

def instrument_fastapi(
        app: FastAPI,
        provider: TracerProvider,
) -> None:
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/metrics",
    )
