from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.db.session import dispose_database_resources, get_database_resources
from app.main import app, lifespan

TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "testuser:testpassword@localhost:5432/platformforge_test"
)

@pytest.fixture(autouse=True)
def clean_database_resources():
    dispose_database_resources()

    yield

    dispose_database_resources()



def test_lifespan_allows_health_requests():
    with TestClient(app) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {
            "status": "healthy",
            "service": "platformforge-api",
        }

def test_lifespan_calls_dispose_on_shutdown():
    with patch("app.main.dispose_database_resources") as mock_dispose:
        with TestClient(app) as client:
            response = client.get("/health")

            assert response.status_code == 200
            mock_dispose.assert_not_called()

        mock_dispose.assert_called_once_with()


@pytest.fixture
def lifecycle():
    owner, engine, factory = object(), Mock(), Mock()
    provider = Mock()
    events = Mock()
    targets = {
        "acquire": ("acquire_sqlalchemy_ownership", owner),
        "url": ("get_database_url", TEST_DATABASE_URL),
        "resources": ("get_database_resources", (engine, factory)),
        "instrument": ("instrument_sqlalchemy", None),
        "dispose": ("dispose_database_resources", None),
        "uninstrument": ("uninstrument_sqlalchemy", None),
        "release": ("release_sqlalchemy_ownership", None),
    }
    with ExitStack() as stack:
        mocks = {}
        for name, (target, result) in targets.items():
            mocks[name] = stack.enter_context(patch(f"app.main.{target}", return_value=result))
            events.attach_mock(mocks[name], name)
        events.attach_mock(provider.shutdown, "shutdown")
        application = FastAPI(lifespan=lifespan)
        application.state.tracer_provider = provider
        handler = Mock(return_value={"status": "ok"})

        @application.get("/probe")
        def probe():
            return handler()

        yield SimpleNamespace(
            app=application, owner=owner, engine=engine, provider=provider,
            events=events, handler=handler, **mocks,
        )


def test_traced_startup_uses_cached_engine_before_accepting_requests(lifecycle):
    def instrument(owner, engine, provider):
        assert owner is lifecycle.owner
        assert engine is lifecycle.engine
        assert provider is lifecycle.app.state.tracer_provider
        lifecycle.handler.assert_not_called()

    lifecycle.instrument.side_effect = instrument
    with TestClient(lifecycle.app) as client:
        assert client.get("/probe").status_code == 200
        lifecycle.handler.assert_called_once_with()
        assert lifecycle.events.mock_calls == [
            call.acquire(), call.url(), call.resources(TEST_DATABASE_URL),
            call.instrument(lifecycle.owner, lifecycle.engine, lifecycle.provider),
        ]


def test_disabled_startup_acquires_ownership_without_engine(lifecycle):
    lifecycle.app.state.tracer_provider = None
    with TestClient(lifecycle.app) as client:
        assert client.get("/probe").status_code == 200
        lifecycle.acquire.assert_called_once_with()
        lifecycle.resources.assert_not_called()
        lifecycle.url.assert_not_called()
        lifecycle.instrument.assert_not_called()
    lifecycle.dispose.assert_called_once_with()
    lifecycle.uninstrument.assert_not_called()
    lifecycle.provider.shutdown.assert_not_called()
    lifecycle.release.assert_called_once_with(lifecycle.owner)


def test_ownership_conflict_only_shuts_down_rejected_provider(lifecycle):
    error = RuntimeError("ownership conflict")
    lifecycle.acquire.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        with TestClient(lifecycle.app):
            pytest.fail("Startup must fail")
    assert caught.value is error
    assert lifecycle.events.mock_calls == [call.acquire(), call.shutdown()]
    lifecycle.handler.assert_not_called()


@pytest.mark.parametrize("step", ["url", "resources", "instrument"])
def test_startup_failure_cleans_resources_without_uninstrumenting(lifecycle, step):
    error = RuntimeError(f"{step} failed")
    getattr(lifecycle, step).side_effect = error
    with pytest.raises(RuntimeError) as caught:
        with TestClient(lifecycle.app):
            pytest.fail("Startup must fail")
    assert caught.value is error
    lifecycle.handler.assert_not_called()
    lifecycle.dispose.assert_called_once_with()
    lifecycle.uninstrument.assert_not_called()
    lifecycle.provider.shutdown.assert_called_once_with()
    lifecycle.release.assert_called_once_with(lifecycle.owner)
    assert lifecycle.events.mock_calls[-3:] == [
        call.dispose(), call.shutdown(), call.release(lifecycle.owner),
    ]


def test_normal_shutdown_cleanup_order(lifecycle):
    with TestClient(lifecycle.app):
        lifecycle.events.reset_mock()
    assert lifecycle.events.mock_calls == [
        call.dispose(), call.uninstrument(lifecycle.owner),
        call.shutdown(), call.release(lifecycle.owner),
    ]


@pytest.mark.parametrize("step", ["dispose", "uninstrument", "shutdown", "release"])
def test_cleanup_failure_preserves_identity_and_attempts_remaining_steps(lifecycle, step):
    error = RuntimeError(f"{step} failed")
    target = lifecycle.provider.shutdown if step == "shutdown" else getattr(lifecycle, step)
    target.side_effect = error
    with pytest.raises(RuntimeError) as caught:
        with TestClient(lifecycle.app):
            lifecycle.events.reset_mock()
    assert caught.value is error
    assert lifecycle.events.mock_calls == [
        call.dispose(), call.uninstrument(lifecycle.owner),
        call.shutdown(), call.release(lifecycle.owner),
    ]


def test_startup_and_cleanup_errors_are_grouped_in_original_order(lifecycle):
    original = RuntimeError("instrument failed")
    disposal = RuntimeError("dispose failed")
    shutdown = RuntimeError("shutdown failed")
    release = RuntimeError("release failed")
    lifecycle.instrument.side_effect = original
    lifecycle.dispose.side_effect = disposal
    lifecycle.provider.shutdown.side_effect = shutdown
    lifecycle.release.side_effect = release
    with pytest.raises(BaseExceptionGroup) as caught:
        with TestClient(lifecycle.app):
            pytest.fail("Startup must fail")
    assert caught.value.exceptions == (original, disposal, shutdown, release)
    lifecycle.uninstrument.assert_not_called()
    lifecycle.handler.assert_not_called()


def test_multiple_shutdown_errors_are_all_preserved(lifecycle):
    errors = [RuntimeError(name) for name in ("dispose", "uninstrument", "shutdown", "release")]
    lifecycle.dispose.side_effect = errors[0]
    lifecycle.uninstrument.side_effect = errors[1]
    lifecycle.provider.shutdown.side_effect = errors[2]
    lifecycle.release.side_effect = errors[3]
    with pytest.raises(BaseExceptionGroup) as caught:
        with TestClient(lifecycle.app):
            pass
    assert caught.value.exceptions == tuple(errors)

def test_lifespan_does_not_dispose_during_requests():
    with patch("app.main.dispose_database_resources") as mock_dispose:
        with TestClient(app) as client:
            client.get("/health")
            client.get("/health")
            client.get("/health")

            mock_dispose.assert_not_called()

        mock_dispose.assert_called_once()

def test_lifespan_disposes_resources_after_shutdown():
    engine_1, factory_1 = get_database_resources(TEST_DATABASE_URL)

    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200

    engine_2, factory_2 = get_database_resources(TEST_DATABASE_URL)

    assert engine_1 is not engine_2
    assert factory_1 is not factory_2


def test_lifespan_disposes_resources_on_error():
    with patch("app.main.dispose_database_resources") as mock_dispose:
        with pytest.raises(RuntimeError,match="Simulated application error"):
            with TestClient(app):
                raise RuntimeError("Simulated application error")

        mock_dispose.assert_called_once_with()
