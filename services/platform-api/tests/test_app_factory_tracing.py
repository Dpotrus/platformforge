from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
import pytest

from app.main import create_app


@pytest.fixture(autouse=True)
def sqlalchemy_lifespan_mocks():
    with (
        patch("app.main.get_database_url", return_value="postgresql+psycopg://test/test"),
        patch("app.main.get_database_resources", return_value=(Mock(), Mock())),
        patch("app.main.instrument_sqlalchemy") as instrument,
        patch("app.main.uninstrument_sqlalchemy") as uninstrument,
    ):
        yield instrument, uninstrument


def test_create_app_disables_tracing_by_default() -> None:
    settings = SimpleNamespace(
        otel_tracing_enabled=False,
        otel_service_name="platformforge-api",
        otel_exporter_otlp_endpoint="http://localhost:4318",
    )

    with (
        patch("app.main.get_settings", return_value=settings),
        patch("app.main.create_tracer_provider") as mock_create_provider,
        patch("app.main.instrument_fastapi") as mock_instrument,
    ):
        application = create_app()

    assert application.state.tracer_provider is None

    mock_create_provider.assert_not_called()
    mock_instrument.assert_not_called()


def test_create_app_enables_tracing_when_configured(sqlalchemy_lifespan_mocks) -> None:
    sql_instrument, _ = sqlalchemy_lifespan_mocks
    settings = SimpleNamespace(
        otel_tracing_enabled=True,
        otel_service_name="platformforge-api-test",
        otel_exporter_otlp_endpoint="http://localhost:4318",
    )

    mock_provider = Mock()

    with (
        patch("app.main.get_settings", return_value=settings),
        patch(
            "app.main.create_tracer_provider",
            return_value=mock_provider,
        ) as mock_create_provider,
        patch("app.main.instrument_fastapi") as mock_instrument,
    ):
        application = create_app()
        with TestClient(application) as client:
            assert client.get("/health").status_code == 200

    assert application.state.tracer_provider is mock_provider

    mock_create_provider.assert_called_once_with(
        service_name="platformforge-api-test",
        endpoint="http://localhost:4318",
    )

    mock_instrument.assert_called_once_with(
        app=application,
        provider=mock_provider,
    )
    assert sql_instrument.call_args.args[2] is mock_instrument.call_args.kwargs["provider"]


def test_lifespan_shuts_down_tracer_provider() -> None:
    settings = SimpleNamespace(
        otel_tracing_enabled=True,
        otel_service_name="platformforge-api-test",
        otel_exporter_otlp_endpoint="http://localhost:4318",
    )

    mock_provider = Mock()

    with (
        patch("app.main.get_settings", return_value=settings),
        patch(
            "app.main.create_tracer_provider",
            return_value=mock_provider,
        ),
        patch("app.main.instrument_fastapi"),
        patch("app.main.dispose_database_resources") as mock_dispose,
    ):
        application = create_app()

        with TestClient(application) as client:
            response = client.get("/health")
            assert response.status_code == 200

        mock_provider.shutdown.assert_called_once_with()
        mock_dispose.assert_called_once_with()


def test_create_app_uses_independent_tracer_providers(sqlalchemy_lifespan_mocks) -> None:
    sql_instrument, sql_uninstrument = sqlalchemy_lifespan_mocks
    settings = SimpleNamespace(
        otel_tracing_enabled=True,
        otel_service_name="platformforge-api-test",
        otel_exporter_otlp_endpoint="http://localhost:4318",
    )

    provider_1 = Mock()
    provider_2 = Mock()

    with (
        patch("app.main.get_settings", return_value=settings),
        patch(
            "app.main.create_tracer_provider",
            side_effect=[provider_1, provider_2],
        ),
        patch("app.main.instrument_fastapi") as mock_instrument,
        patch("app.main.dispose_database_resources"),
    ):
        app_1 = create_app()
        app_2 = create_app()

        assert app_1 is not app_2
        assert app_1.state.tracer_provider is provider_1
        assert app_2.state.tracer_provider is provider_2

        with TestClient(app_1):
            pass

        provider_1.shutdown.assert_called_once_with()
        provider_2.shutdown.assert_not_called()
        sql_uninstrument.assert_called_once()
        assert sql_instrument.call_args_list[0].args[2] is provider_1

        with TestClient(app_2):
            pass

        provider_2.shutdown.assert_called_once_with()
        assert sql_uninstrument.call_count == 2
        assert sql_instrument.call_args_list[1].args[2] is provider_2
        assert sql_instrument.call_args_list[0].args[0] is not sql_instrument.call_args_list[1].args[0]

        assert mock_instrument.call_count == 2
