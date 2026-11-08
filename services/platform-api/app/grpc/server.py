from concurrent import futures

import grpc
from sqlalchemy.orm import Session, sessionmaker

from app.grpc.applications import ApplicationServiceServicer
from platformforge.v1 import applications_pb2_grpc

from app.config import get_settings
from app.db.session import get_database_resources, dispose_database_resources

from app.observability.tracing import (
    acquire_sqlalchemy_ownership,
    create_tracer_provider,
    instrument_sqlalchemy,
    release_sqlalchemy_ownership,
    uninstrument_sqlalchemy,
)

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.grpc import server_interceptor

from grpc_health.v1 import health, health_pb2, health_pb2_grpc


def create_grpc_server(
        session_factory: sessionmaker[Session],
        tracer_provider: TracerProvider | None = None,
) -> grpc.Server:
    interceptors = []

    if tracer_provider is not None:
        interceptors.append(
            server_interceptor(
                tracer_provider=tracer_provider,
            )
        )

    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=10),
        interceptors=interceptors,
    )

    applications_pb2_grpc.add_ApplicationServiceServicer_to_server(
        ApplicationServiceServicer(
            session_factory=session_factory,
        ),
        server,
    )

    health_servicer = health.HealthServicer()

    health_pb2_grpc.add_HealthServicer_to_server(
        health_servicer,
        server,
    )

    health_servicer.set(
        "",
        health_pb2.HealthCheckResponse.SERVING,
    )

    health_servicer.set(
        "platformforge.v1.ApplicationService",
        health_pb2.HealthCheckResponse.SERVING,
    )

    return server

def run_grpc_server() -> None:
    server: grpc.Server | None = None
    owner: object | None = None
    started = False
    errors: list[BaseException] = []
    tracer_provider: TracerProvider | None = None
    sqlalchemy_instrumented = False

    try:
        owner = acquire_sqlalchemy_ownership()

        settings = get_settings()

        if settings.otel_tracing_enabled:
            tracer_provider = create_tracer_provider(
                service_name=settings.otel_grpc_service_name,
                endpoint=settings.otel_exporter_otlp_endpoint,
            )

        engine, session_factory = get_database_resources(
            settings.database_url,
        )

        if tracer_provider is not None:
            instrument_sqlalchemy(owner, engine, tracer_provider)
            sqlalchemy_instrumented = True

        server = create_grpc_server(
            session_factory=session_factory,
            tracer_provider=tracer_provider,
        )

        address = f"{settings.grpc_host}:{settings.grpc_port}"
        bound_port = server.add_insecure_port(address)

        if bound_port == 0:
            raise RuntimeError(
                f"Failed to bind gRPC server to {address}"
            )

        server.start()
        started = True

        server.wait_for_termination()

    except KeyboardInterrupt:
        pass
    except BaseException as exc:
        errors.append(exc)
    finally:
        try:
            if server is not None and started:
                stop_event = server.stop(grace=5)
                stop_event.wait(timeout=10)
        except BaseException as exc:
            errors.append(exc)

        try:
            if owner is not None:
                dispose_database_resources()
        except BaseException as exc:
            errors.append(exc)

        try:
            if sqlalchemy_instrumented:
                uninstrument_sqlalchemy(owner)
        except BaseException as exc:
            errors.append(exc)

        try:
            if tracer_provider is not None:
                tracer_provider.shutdown()
        except BaseException as exc:
            errors.append(exc)

        try:
            if owner is not None:
                release_sqlalchemy_ownership(owner)
        except BaseException as exc:
            errors.append(exc)

    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise BaseExceptionGroup(
            "gRPC server lifecycle failed",
            errors,
        )

if __name__ == "__main__":
    run_grpc_server()