from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock, patch, call

from app.grpc.server import create_grpc_server, run_grpc_server
import pytest


@pytest.fixture(autouse=True)
def mock_sqlalchemy_ownership() -> Iterator[None]:
    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=object(),
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
        ),
    ):
        yield


def test_create_grpc_server_registers_application_servicer() -> None:
    session_factory = Mock()
    grpc_server = Mock()

    with (
        patch(
            "app.grpc.server.grpc.server",
            return_value=grpc_server,
        ) as mock_grpc_server,
        patch(
            "app.grpc.server.applications_pb2_grpc."
            "add_ApplicationServiceServicer_to_server",
        ) as mock_register,
    ):
        result = create_grpc_server(session_factory)

    assert result is grpc_server

    mock_grpc_server.assert_called_once()

    executor = mock_grpc_server.call_args.args[0]
    assert isinstance(executor, ThreadPoolExecutor)
    assert executor._max_workers == 10

    mock_register.assert_called_once()

    registered_servicer, registered_server = (
        mock_register.call_args.args
    )

    assert registered_server is grpc_server
    assert registered_servicer._session_factory is session_factory

    executor.shutdown(wait=True)


def test_create_grpc_server_uses_tracing_interceptor() -> None:
    session_factory = Mock()
    tracer_provider = Mock()
    grpc_server = Mock()
    interceptor = Mock()

    with (
        patch(
            "app.grpc.server.server_interceptor",
            return_value=interceptor,
        ) as mock_interceptor,
        patch(
            "app.grpc.server.grpc.server",
            return_value=grpc_server,
        ) as mock_grpc_server,
        patch(
            "app.grpc.server.applications_pb2_grpc."
            "add_ApplicationServiceServicer_to_server",
        ),
    ):
        result = create_grpc_server(
            session_factory=session_factory,
            tracer_provider=tracer_provider,
        )

    assert result is grpc_server

    mock_interceptor.assert_called_once_with(
        tracer_provider=tracer_provider,
    )

    mock_grpc_server.assert_called_once()

    assert mock_grpc_server.call_args.kwargs["interceptors"] == [
        interceptor,
    ]

    executor = mock_grpc_server.call_args.args[0]
    executor.shutdown(wait=True)


def test_run_grpc_server_starts_and_stops_cleanly() -> None:
    settings = Mock()
    settings.otel_tracing_enabled = False
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    stop_event = Mock()
    grpc_server.stop.return_value = stop_event

    with (
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
        ) as mock_dispose,
    ):
        run_grpc_server()

    grpc_server.add_insecure_port.assert_called_once_with(
        "127.0.0.1:50051"
    )
    grpc_server.start.assert_called_once_with()
    grpc_server.wait_for_termination.assert_called_once_with()

    grpc_server.stop.assert_called_once_with(grace=5)
    stop_event.wait.assert_called_once_with(timeout=10)

    mock_dispose.assert_called_once_with()


def test_run_grpc_server_cleans_up_when_port_binding_fails() -> None:
    settings = Mock()
    settings.otel_tracing_enabled = False
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 0

    with (
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
        ) as mock_dispose,
    ):
        with pytest.raises(
                RuntimeError,
                match="Failed to bind gRPC server",
        ):
            run_grpc_server()

    grpc_server.add_insecure_port.assert_called_once_with(
        "127.0.0.1:50051"
    )

    grpc_server.start.assert_not_called()
    grpc_server.stop.assert_not_called()
    grpc_server.wait_for_termination.assert_not_called()

    mock_dispose.assert_called_once_with()


def test_run_grpc_server_cleans_up_when_start_fails() -> None:
    settings = Mock()
    settings.otel_tracing_enabled = False
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.start.side_effect = RuntimeError("Server startup failed")

    with (
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
        ) as mock_dispose,
    ):
        with pytest.raises(
                RuntimeError,
                match="Server startup failed",
        ):
            run_grpc_server()

    grpc_server.add_insecure_port.assert_called_once_with(
        "127.0.0.1:50051"
    )

    grpc_server.start.assert_called_once_with()
    grpc_server.wait_for_termination.assert_not_called()

    grpc_server.stop.assert_not_called()

    mock_dispose.assert_called_once_with()


def test_run_grpc_server_releases_sqlalchemy_ownership() -> None:
    settings = Mock()
    settings.otel_tracing_enabled = False
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    owner = object()
    lifecycle = Mock()

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ) as mock_acquire,
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ) as mock_release,
    ):
        run_grpc_server()

    mock_acquire.assert_called_once_with()
    mock_release.assert_called_once_with(owner)

    assert lifecycle.mock_calls == [
        call.dispose(),
        call.release(owner),
    ]

    grpc_server.start.assert_called_once_with()
    grpc_server.stop.assert_called_once_with(grace=5)


def test_run_grpc_server_creates_and_shuts_down_tracer_provider() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051
    settings.otel_tracing_enabled = True
    settings.otel_grpc_service_name = "platformforge-grpc"
    settings.otel_exporter_otlp_endpoint = "http://localhost:4318"

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    owner = object()
    lifecycle = Mock()
    tracer_provider = Mock()
    engine = Mock()
    session_factory = Mock()

    tracer_provider.shutdown.side_effect = lifecycle.shutdown

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ),
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
            return_value=tracer_provider,
        ) as mock_create_provider,
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(engine, session_factory),
        ) as mock_get_resources,
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ) as mock_create_server,
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ),
        patch(
            "app.grpc.server.instrument_sqlalchemy",
        ) as mock_instrument,
        patch(
            "app.grpc.server.uninstrument_sqlalchemy",
            side_effect=lifecycle.uninstrument
        ) as mock_uninstrument,
    ):
        run_grpc_server()

    mock_create_provider.assert_called_once_with(
        service_name="platformforge-grpc",
        endpoint="http://localhost:4318",
    )

    tracer_provider.shutdown.assert_called_once_with()

    assert lifecycle.mock_calls == [
        call.dispose(),
        call.uninstrument(owner),
        call.shutdown(),
        call.release(owner),
    ]

    mock_get_resources.assert_called_once_with(
        settings.database_url,
    )


    mock_create_server.assert_called_once_with(
        session_factory=session_factory,
        tracer_provider=tracer_provider,
    )


    mock_instrument.assert_called_once_with(
            owner,
            engine,
            tracer_provider,
        )

    mock_uninstrument.assert_called_once_with(owner)



def test_run_grpc_server_does_not_create_tracer_when_disabled() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051
    settings.otel_tracing_enabled = False

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    with (
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
        ) as mock_create_provider,
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
        ) as mock_dispose,
    ):
        run_grpc_server()

    mock_create_provider.assert_not_called()
    mock_dispose.assert_called_once_with()

    grpc_server.start.assert_called_once_with()
    grpc_server.stop.assert_called_once_with(grace=5)


def test_run_grpc_server_continues_cleanup_when_uninstrument_fails() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051
    settings.otel_tracing_enabled = True
    settings.otel_grpc_service_name = "platformforge-grpc"
    settings.otel_exporter_otlp_endpoint = "http://localhost:4318"

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    owner = object()
    lifecycle = Mock()
    tracer_provider = Mock()

    cleanup_error = RuntimeError("SQLAlchemy uninstrument failed")
    lifecycle.uninstrument.side_effect = cleanup_error
    tracer_provider.shutdown.side_effect = lifecycle.shutdown

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ),
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
            return_value=tracer_provider,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.instrument_sqlalchemy",
        ),
        patch(
            "app.grpc.server.uninstrument_sqlalchemy",
            side_effect=lifecycle.uninstrument,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            run_grpc_server()

    assert exc_info.value is cleanup_error

    assert lifecycle.mock_calls == [
        call.dispose(),
        call.uninstrument(owner),
        call.shutdown(),
        call.release(owner),
    ]

    grpc_server.stop.assert_called_once_with(grace=5)
    tracer_provider.shutdown.assert_called_once_with()

def test_run_grpc_server_preserves_multiple_cleanup_errors() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.grpc_host = "127.0.0.1"
    settings.grpc_port = 50051
    settings.otel_tracing_enabled = True
    settings.otel_grpc_service_name = "platformforge-grpc"
    settings.otel_exporter_otlp_endpoint = "http://localhost:4318"

    grpc_server = Mock()
    grpc_server.add_insecure_port.return_value = 50051
    grpc_server.wait_for_termination.side_effect = KeyboardInterrupt

    owner = object()
    lifecycle = Mock()
    tracer_provider = Mock()

    uninstrument_error = RuntimeError("SQLAlchemy uninstrument failed")
    shutdown_error = RuntimeError("Tracer provider shutdown failed")

    lifecycle.uninstrument.side_effect = uninstrument_error
    lifecycle.shutdown.side_effect = shutdown_error
    tracer_provider.shutdown.side_effect = lifecycle.shutdown

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ),
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
            return_value=tracer_provider,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(Mock(), Mock()),
        ),
        patch(
            "app.grpc.server.create_grpc_server",
            return_value=grpc_server,
        ),
        patch(
            "app.grpc.server.instrument_sqlalchemy",
        ),
        patch(
            "app.grpc.server.uninstrument_sqlalchemy",
            side_effect=lifecycle.uninstrument,
        ),
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ),
    ):
        with pytest.raises(BaseExceptionGroup) as exc_info:
            run_grpc_server()

    assert len(exc_info.value.exceptions) == 2
    assert exc_info.value.exceptions[0] is uninstrument_error
    assert exc_info.value.exceptions[1] is shutdown_error

    assert lifecycle.mock_calls == [
        call.dispose(),
        call.uninstrument(owner),
        call.shutdown(),
        call.release(owner),
    ]

    grpc_server.stop.assert_called_once_with(grace=5)
    tracer_provider.shutdown.assert_called_once_with()


def test_run_grpc_server_cleans_up_when_sqlalchemy_instrumentation_fails() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.otel_tracing_enabled = True
    settings.otel_grpc_service_name = "platformforge-grpc"
    settings.otel_exporter_otlp_endpoint = "http://localhost:4318"

    owner = object()
    engine = Mock()
    session_factory = Mock()
    tracer_provider = Mock()
    lifecycle = Mock()

    instrumentation_error = RuntimeError(
        "SQLAlchemy instrumentation failed"
    )

    lifecycle.instrument.side_effect = instrumentation_error
    tracer_provider.shutdown.side_effect = lifecycle.shutdown

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ),
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
            return_value=tracer_provider,
        ),
        patch(
            "app.grpc.server.get_database_resources",
            return_value=(engine, session_factory),
        ),
        patch(
            "app.grpc.server.instrument_sqlalchemy",
            side_effect=lifecycle.instrument,
        ) as mock_instrument,
        patch(
            "app.grpc.server.uninstrument_sqlalchemy",
        ) as mock_uninstrument,
        patch(
            "app.grpc.server.create_grpc_server",
        ) as mock_create_server,
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            run_grpc_server()

    assert exc_info.value is instrumentation_error

    mock_instrument.assert_called_once_with(
        owner,
        engine,
        tracer_provider,
    )

    mock_uninstrument.assert_not_called()
    mock_create_server.assert_not_called()

    assert lifecycle.mock_calls == [
        call.instrument(owner, engine, tracer_provider),
        call.dispose(),
        call.shutdown(),
        call.release(owner),
    ]


def test_run_grpc_server_cleans_up_when_tracer_provider_creation_fails() -> None:
    settings = Mock()
    settings.database_url = (
        "postgresql+psycopg://test:test@localhost:5432/testdb"
    )
    settings.otel_tracing_enabled = True
    settings.otel_grpc_service_name = "platformforge-grpc"
    settings.otel_exporter_otlp_endpoint = "http://localhost:4318"

    owner = object()
    lifecycle = Mock()

    creation_error = RuntimeError("Tracer provider creation failed")

    with (
        patch(
            "app.grpc.server.acquire_sqlalchemy_ownership",
            return_value=owner,
        ),
        patch(
            "app.grpc.server.get_settings",
            return_value=settings,
        ),
        patch(
            "app.grpc.server.create_tracer_provider",
            side_effect=creation_error,
        ) as mock_create_provider,
        patch(
            "app.grpc.server.get_database_resources",
        ) as mock_get_resources,
        patch(
            "app.grpc.server.create_grpc_server",
        ) as mock_create_server,
        patch(
            "app.grpc.server.dispose_database_resources",
            side_effect=lifecycle.dispose,
        ),
        patch(
            "app.grpc.server.release_sqlalchemy_ownership",
            side_effect=lifecycle.release,
        ),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            run_grpc_server()

    assert exc_info.value is creation_error

    mock_create_provider.assert_called_once_with(
        service_name="platformforge-grpc",
        endpoint="http://localhost:4318",
    )

    mock_get_resources.assert_not_called()
    mock_create_server.assert_not_called()

    assert lifecycle.mock_calls == [
        call.dispose(),
        call.release(owner),
    ]


def test_create_grpc_server_without_tracing_interceptor() -> None:
    session_factory = Mock()
    grpc_server = Mock()

    with (
        patch("app.grpc.server.server_interceptor") as mock_interceptor,
        patch(
            "app.grpc.server.grpc.server",
            return_value=grpc_server,
        ) as mock_grpc_server,
        patch(
            "app.grpc.server.applications_pb2_grpc."
            "add_ApplicationServiceServicer_to_server",
        ),
    ):
        result = create_grpc_server(
            session_factory=session_factory,
            tracer_provider=None,
        )

    assert result is grpc_server

    mock_interceptor.assert_not_called()

    assert mock_grpc_server.call_args.kwargs["interceptors"] == []

    executor = mock_grpc_server.call_args.args[0]
    executor.shutdown(wait=True)
