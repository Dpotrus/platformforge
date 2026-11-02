import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from threading import Event, Thread
from unittest.mock import Mock

import pytest
from sqlalchemy.engine import Engine
from opentelemetry.sdk.trace import TracerProvider

from app.observability import tracing

from fastapi import FastAPI
from fastapi.testclient import TestClient

from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind

from app.observability.tracing import instrument_fastapi

from unittest.mock import patch

from app.observability.tracing import create_tracer_provider


def test_create_tracer_provider_sets_service_name() -> None:
    provider = create_tracer_provider(
        service_name="platformforge-api",
    )

    try:
        assert provider.resource.attributes["service.name"] == "platformforge-api"
    finally:
        provider.shutdown()


def test_create_tracer_provider_configures_otlp_exporter() -> None:
    with patch(
            "app.observability.tracing.OTLPSpanExporter"
    ) as mock_exporter:
        provider = create_tracer_provider(
            service_name="platformforge-api",
            endpoint="http://localhost:4318",
        )

        try:
            mock_exporter.assert_called_once_with(
                endpoint="http://localhost:4318/v1/traces",
                timeout=5,
            )
        finally:
            provider.shutdown()


def test_create_tracer_provider_handles_trailing_slash() -> None:
    with patch(
            "app.observability.tracing.OTLPSpanExporter"
    ) as mock_exporter:
        provider = create_tracer_provider(
            service_name="platformforge-api",
            endpoint="http://localhost:4318/",
        )

        try:
            mock_exporter.assert_called_once_with(
                endpoint="http://localhost:4318/v1/traces",
                timeout=5,
            )
        finally:
            provider.shutdown()


def test_instrument_fastapi_creates_http_span() -> None:
    provider = create_tracer_provider(
        service_name="platformforge-api-test",
    )

    exporter = InMemorySpanExporter()
    provider.add_span_processor(
        SimpleSpanProcessor(exporter)
    )

    test_app = FastAPI()

    @test_app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "healthy"}

    instrument_fastapi(
        app=test_app,
        provider=provider,
    )

    try:
        with TestClient(test_app) as client:
            response = client.get("/health")

        assert response.status_code == 200

        spans = exporter.get_finished_spans()

        assert any(
            span.name == "GET /health"
            for span in spans
        )
    finally:
        provider.shutdown()
        exporter.clear()


@pytest.fixture
def sqlalchemy_instrumentor() -> Iterator[Mock]:
    instrumentor = Mock(is_instrumented_by_opentelemetry=False)

    def activate(**kwargs: object) -> None:
        instrumentor.is_instrumented_by_opentelemetry = True

    def deactivate() -> None:
        instrumentor.is_instrumented_by_opentelemetry = False

    instrumentor.instrument.side_effect = activate
    instrumentor.uninstrument.side_effect = deactivate
    with patch.object(tracing, "SQLAlchemyInstrumentor", return_value=instrumentor):
        yield instrumentor


@pytest.fixture
def sqlalchemy_owner(sqlalchemy_instrumentor: Mock) -> Iterator[object]:
    owner = tracing.acquire_sqlalchemy_ownership()
    try:
        yield owner
    finally:
        tracing.uninstrument_sqlalchemy(owner)
        tracing.release_sqlalchemy_ownership(owner)


def test_sqlalchemy_ownership_can_be_acquired_and_released(
        sqlalchemy_instrumentor: Mock,
) -> None:
    owner = tracing.acquire_sqlalchemy_ownership()
    tracing.release_sqlalchemy_ownership(owner)
    tracing.release_sqlalchemy_ownership(owner)
    sqlalchemy_instrumentor.instrument.assert_not_called()
    sqlalchemy_instrumentor.uninstrument.assert_not_called()


def test_sqlalchemy_rejects_concurrent_owner(sqlalchemy_owner: object) -> None:
    with pytest.raises(RuntimeError, match="Another application owns"):
        tracing.acquire_sqlalchemy_ownership()


def test_sqlalchemy_acquisition_does_not_wait_for_instrumentation(
        sqlalchemy_owner: object,
        sqlalchemy_instrumentor: Mock,
) -> None:
    entered, finish, acquisition_finished = Event(), Event(), Event()
    errors: list[BaseException] = []

    def activate(**kwargs: object) -> None:
        entered.set()
        if not finish.wait(timeout=5):
            raise RuntimeError("Test did not release instrumentation")
        sqlalchemy_instrumentor.is_instrumented_by_opentelemetry = True

    def instrument() -> None:
        try:
            tracing.instrument_sqlalchemy(sqlalchemy_owner, Mock(spec=Engine), Mock(spec=TracerProvider))
        except BaseException as exc:
            errors.append(exc)

    def acquire() -> None:
        try:
            with pytest.raises(RuntimeError, match="state is busy"):
                tracing.acquire_sqlalchemy_ownership()
        except BaseException as exc:
            errors.append(exc)
        finally:
            acquisition_finished.set()

    sqlalchemy_instrumentor.instrument.side_effect = activate
    worker = Thread(target=instrument)
    contender = Thread(target=acquire)
    worker.start()
    try:
        assert entered.wait(timeout=2)
        contender.start()
        assert acquisition_finished.wait(timeout=2), "Ownership acquisition blocked"
    finally:
        finish.set()
        worker.join(timeout=5)
        if contender.ident is not None:
            contender.join(timeout=5)
    assert not worker.is_alive()
    assert not contender.is_alive()
    assert not errors


@pytest.mark.parametrize("operation", ["instrument", "uninstrument", "release"])
def test_sqlalchemy_rejects_wrong_owner(
        sqlalchemy_owner: object,
        sqlalchemy_instrumentor: Mock,
        operation: str,
) -> None:
    with pytest.raises(RuntimeError, match="ownership|belongs to another"):
        if operation == "instrument":
            tracing.instrument_sqlalchemy(object(), Mock(spec=Engine), Mock(spec=TracerProvider))
        elif operation == "uninstrument":
            tracing.uninstrument_sqlalchemy(object())
        else:
            tracing.release_sqlalchemy_ownership(object())
    sqlalchemy_instrumentor.instrument.assert_not_called()
    sqlalchemy_instrumentor.uninstrument.assert_not_called()


def test_sqlalchemy_uses_exact_engine_and_provider(
        sqlalchemy_owner: object,
        sqlalchemy_instrumentor: Mock,
) -> None:
    engine = Mock(spec=Engine)
    provider = Mock(spec=TracerProvider)
    tracing.instrument_sqlalchemy(sqlalchemy_owner, engine, provider)
    sqlalchemy_instrumentor.instrument.assert_called_once_with(
        engine=engine, tracer_provider=provider, raise_exception_on_conflict=True,
    )
    assert sqlalchemy_instrumentor.instrument.call_args.kwargs["engine"] is engine
    assert sqlalchemy_instrumentor.instrument.call_args.kwargs["tracer_provider"] is provider


def test_sqlalchemy_rejects_duplicate_activation_even_after_cleanup(
        sqlalchemy_owner: object,
        sqlalchemy_instrumentor: Mock,
) -> None:
    engine, provider = Mock(spec=Engine), Mock(spec=TracerProvider)
    tracing.instrument_sqlalchemy(sqlalchemy_owner, engine, provider)
    with pytest.raises(RuntimeError, match="already instrumented"):
        tracing.instrument_sqlalchemy(sqlalchemy_owner, engine, provider)
    tracing.uninstrument_sqlalchemy(sqlalchemy_owner)
    with pytest.raises(RuntimeError, match="already instrumented"):
        tracing.instrument_sqlalchemy(sqlalchemy_owner, engine, provider)
    sqlalchemy_instrumentor.instrument.assert_called_once()


def test_sqlalchemy_cleanup_is_idempotent(
        sqlalchemy_owner: object,
        sqlalchemy_instrumentor: Mock,
) -> None:
    tracing.uninstrument_sqlalchemy(sqlalchemy_owner)
    sqlalchemy_instrumentor.uninstrument.assert_not_called()
    tracing.instrument_sqlalchemy(sqlalchemy_owner, Mock(spec=Engine), Mock(spec=TracerProvider))
    tracing.uninstrument_sqlalchemy(sqlalchemy_owner)
    tracing.uninstrument_sqlalchemy(sqlalchemy_owner)
    sqlalchemy_instrumentor.uninstrument.assert_called_once_with()
    assert sqlalchemy_instrumentor.is_instrumented_by_opentelemetry is False


def test_sqlalchemy_cannot_release_active_owner(sqlalchemy_owner: object) -> None:
    tracing.instrument_sqlalchemy(sqlalchemy_owner, Mock(spec=Engine), Mock(spec=TracerProvider))
    with pytest.raises(RuntimeError, match="before ownership"):
        tracing.release_sqlalchemy_ownership(sqlalchemy_owner)


def test_sqlalchemy_sequential_lifecycles_use_different_providers(
        sqlalchemy_instrumentor: Mock,
) -> None:
    engine = Mock(spec=Engine)
    providers = [Mock(spec=TracerProvider), Mock(spec=TracerProvider)]
    owners = []
    for provider in providers:
        owner = tracing.acquire_sqlalchemy_ownership()
        owners.append(owner)
        try:
            tracing.instrument_sqlalchemy(owner, engine, provider)
        finally:
            tracing.uninstrument_sqlalchemy(owner)
            tracing.release_sqlalchemy_ownership(owner)
    assert owners[0] is not owners[1]
    assert sqlalchemy_instrumentor.instrument.call_count == 2
    for call, provider in zip(sqlalchemy_instrumentor.instrument.call_args_list, providers):
        assert call.kwargs["engine"] is engine
        assert call.kwargs["tracer_provider"] is provider
    assert sqlalchemy_instrumentor.uninstrument.call_count == 2


@pytest.mark.parametrize("activation_time", ["before_ownership", "after_ownership"])
def test_sqlalchemy_rejects_external_activation_without_removing_it(
        sqlalchemy_instrumentor: Mock,
        activation_time: str,
) -> None:
    owner = None
    try:
        if activation_time == "after_ownership":
            owner = tracing.acquire_sqlalchemy_ownership()
        sqlalchemy_instrumentor.is_instrumented_by_opentelemetry = True
        with pytest.raises(RuntimeError, match="External SQLAlchemy instrumentation"):
            if owner is None:
                tracing.acquire_sqlalchemy_ownership()
            else:
                tracing.instrument_sqlalchemy(owner, Mock(spec=Engine), Mock(spec=TracerProvider))
        if owner is not None:
            tracing.uninstrument_sqlalchemy(owner)
        assert sqlalchemy_instrumentor.is_instrumented_by_opentelemetry is True
        sqlalchemy_instrumentor.instrument.assert_not_called()
        sqlalchemy_instrumentor.uninstrument.assert_not_called()
    finally:
        if owner is not None:
            tracing.release_sqlalchemy_ownership(owner)


@pytest.mark.parametrize(
    "failure",
    ["activation_raises", "activation_inactive", "cleanup_raises", "cleanup_stays_active"],
)
def test_sqlalchemy_uncertain_failures_require_process_restart(failure: str) -> None:
    # A fresh interpreter isolates the intentionally permanent restart state.
    script = textwrap.dedent('''
        import sys
        from unittest.mock import Mock, patch
        import pytest
        from sqlalchemy.engine import Engine
        from opentelemetry.sdk.trace import TracerProvider
        from app.observability import tracing

        failure = sys.argv[1]
        instrumentor = Mock(is_instrumented_by_opentelemetry=False)
        engine, provider = Mock(spec=Engine), Mock(spec=TracerProvider)
        original_error = RuntimeError("simulated partial failure")

        def activate(**kwargs):
            if failure == "activation_raises":
                # Partial patches can exist despite this flag staying false.
                raise original_error
            if failure != "activation_inactive":
                instrumentor.is_instrumented_by_opentelemetry = True

        def deactivate():
            if failure == "cleanup_raises":
                raise original_error
            if failure != "cleanup_stays_active":
                instrumentor.is_instrumented_by_opentelemetry = False

        instrumentor.instrument.side_effect = activate
        instrumentor.uninstrument.side_effect = deactivate
        with patch.object(tracing, "SQLAlchemyInstrumentor", return_value=instrumentor):
            owner = tracing.acquire_sqlalchemy_ownership()
            if failure.startswith("activation"):
                with pytest.raises(RuntimeError) as caught:
                    tracing.instrument_sqlalchemy(owner, engine, provider)
                if failure == "activation_raises":
                    assert caught.value is original_error
                else:
                    assert "did not become active" in str(caught.value)
                instrumentor.uninstrument.assert_not_called()
            else:
                tracing.instrument_sqlalchemy(owner, engine, provider)
                with pytest.raises(RuntimeError) as caught:
                    tracing.uninstrument_sqlalchemy(owner)
                if failure == "cleanup_raises":
                    assert caught.value is original_error
                else:
                    assert "remained active" in str(caught.value)

            cleanup_calls = instrumentor.uninstrument.call_count
            with pytest.raises(RuntimeError, match="process restart"):
                tracing.instrument_sqlalchemy(owner, engine, provider)
            with pytest.raises(RuntimeError, match="process restart"):
                tracing.uninstrument_sqlalchemy(owner)
            assert instrumentor.uninstrument.call_count == cleanup_calls
            instrumentor.instrument.assert_called_once()
            tracing.release_sqlalchemy_ownership(owner)
            with pytest.raises(RuntimeError, match="process restart"):
                tracing.acquire_sqlalchemy_ownership()
    ''')
    result = subprocess.run(
        [sys.executable, "-B", "-c", script, failure],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_instrument_fastapi_excludes_metrics_endpoint() -> None:
    provider = create_tracer_provider(
        service_name="platformforge-api-test",
    )

    exporter = InMemorySpanExporter()

    provider.add_span_processor(
        SimpleSpanProcessor(exporter)
    )

    test_app = FastAPI()

    @test_app.get("/metrics")
    def metrics() -> dict[str, str]:
        return {"status": "ok"}

    instrument_fastapi(
        app=test_app,
        provider=provider,
    )

    try:
        with TestClient(test_app) as client:
            response = client.get("/metrics")

        assert response.status_code == 200

        spans = exporter.get_finished_spans()

        assert not any(
            span.kind == SpanKind.SERVER
            and span.attributes.get("http.route") == "/metrics"
            for span in spans
        )
    finally:
        provider.shutdown()
        exporter.clear()

def test_sqlalchemy_real_instrumentation_creates_client_span() -> None:
    script = textwrap.dedent("""
    from opentelemetry import trace
    from sqlalchemy import create_engine, text

    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    from app.observability.tracing import (
    acquire_sqlalchemy_ownership,
    create_tracer_provider,
    instrument_sqlalchemy,
    release_sqlalchemy_ownership,
    uninstrument_sqlalchemy,
    )

    engine = create_engine("sqlite+pysqlite:///:memory:")

    provider = create_tracer_provider(
        service_name="platformforge-sqlalchemy-test",
    )

    exporter = InMemorySpanExporter()

    provider.add_span_processor(
        SimpleSpanProcessor(exporter)
    )

    owner = acquire_sqlalchemy_ownership()
    instrument_sqlalchemy(owner, engine, provider)

    try:
        tracer = trace.get_tracer(
            "platformforge-sqlalchemy-test",
            tracer_provider=provider,
        )

        with tracer.start_as_current_span("parent-operation") as parent_span:
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                assert result.scalar_one() == 1

            from opentelemetry.trace import SpanKind

            spans = exporter.get_finished_spans()

            client_spans = [
                span
                for span in spans
                if span.kind == SpanKind.CLIENT
            ]

            assert len(client_spans) >= 1, (
                f"Expected a SQLAlchemy CLIENT span, got: {spans}"
            )

            sql_spans = [
                span
                for span in client_spans
                if span.attributes
                and span.attributes.get("db.statement") == "SELECT 1"
            ]

            assert len(sql_spans) == 1

            sql_span = sql_spans[0]

            assert sql_span.attributes["db.system"] == "sqlite"
            assert sql_span.attributes["db.name"] == ":memory:"

            assert parent_span.get_span_context().is_valid

            parent_context = parent_span.get_span_context()

            assert sql_span.context.trace_id == parent_context.trace_id

            assert sql_span.parent is not None
            assert sql_span.parent.span_id == parent_context.span_id
    finally:
        engine.dispose()
        uninstrument_sqlalchemy(owner)
        provider.shutdown()
        release_sqlalchemy_ownership(owner)
""")

    result = subprocess.run(
        [sys.executable, "-B", "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stdout + result.stderr