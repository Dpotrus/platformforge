
from threading import Event, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import session as session_module
from app.db.session import (
    create_database_engine,
    create_session_factory,
    dispose_database_resources,
    get_database_resources,
    get_database_url,
    get_db_session,
)

TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "testuser:testpassword@localhost:5432/platformforge_test"
)

SECOND_DATABASE_URL = (
    "postgresql+psycopg://"
    "testuser:testpassword@localhost:5432/platformforge_second"
)


@pytest.fixture(autouse=True)
def clean_database_resources():
    get_settings.cache_clear()
    dispose_database_resources()

    yield

    dispose_database_resources()
    get_settings.cache_clear()



def test_get_database_url_returns_environment_variable():
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": TEST_DATABASE_URL},
    ):
        assert get_database_url() == TEST_DATABASE_URL



def test_get_database_url_raises_when_missing():
    with patch.dict("os.environ", {}, clear=True):
        with patch(
                "app.db.session.get_settings",
                side_effect=lambda: Settings(_env_file=None),
        ):
            with pytest.raises(
                    ValidationError,
                    match="database_url",
            ):
                get_database_url()


@pytest.mark.parametrize(
    "invalid_url",
    [
        "sqlite:///test.db",
        "postgresql://localhost/test",
        "mysql+pymysql://localhost/test",
        "invalid-url",
    ],
)
def test_get_database_url_rejects_invalid_dialect(invalid_url: str,):
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": invalid_url},
    ):
        with pytest.raises(
                ValidationError,
                match="database_url",
        ):
            get_database_url()


def test_create_database_engine_uses_postgresql_psycopg():
    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        assert isinstance(engine, Engine)
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
    finally:
        engine.dispose()


def test_create_database_engine_enables_pool_pre_ping():
    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        assert engine.pool._pre_ping is True
    finally:
        engine.dispose()


def test_create_session_factory_creates_session():
    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        session_factory = create_session_factory(engine)

        with session_factory() as session:
            assert isinstance(session, Session)
            assert session.bind is engine
    finally:
        engine.dispose()


def test_create_session_factory_disables_autoflush():
    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        session_factory = create_session_factory(engine)

        with session_factory() as session:
            assert session.autoflush is False
    finally:
        engine.dispose()


def test_create_session_factory_disables_expire_on_commit():
    engine = create_database_engine(TEST_DATABASE_URL)

    try:
        session_factory = create_session_factory(engine)

        with session_factory() as session:
            assert session.expire_on_commit is False
    finally:
        engine.dispose()


def test_get_database_resources_reuses_engine_and_factory():
    engine_1, factory_1 = get_database_resources(
        TEST_DATABASE_URL
    )
    engine_2, factory_2 = get_database_resources(
        TEST_DATABASE_URL
    )

    assert engine_1 is engine_2
    assert factory_1 is factory_2


def test_get_database_resources_separates_database_urls():
    engine_1, factory_1 = get_database_resources(
        TEST_DATABASE_URL
    )
    engine_2, factory_2 = get_database_resources(
        SECOND_DATABASE_URL
    )

    assert engine_1 is not engine_2
    assert factory_1 is not factory_2


def test_get_database_resources_creates_separate_sessions():
    engine, session_factory = get_database_resources(
        TEST_DATABASE_URL
    )

    with session_factory() as session_1:
        with session_factory() as session_2:
            assert session_1 is not session_2
            assert session_1.bind is engine
            assert session_2.bind is engine


def test_get_database_resources_disposes_engine_when_factory_fails():
    mock_engine = MagicMock(spec=Engine)

    with (patch("app.db.session.create_database_engine", return_value=mock_engine,)
        , patch(
        "app.db.session.create_session_factory",
        side_effect=RuntimeError("Factory creation failed"),
    ), ):
        with pytest.raises(RuntimeError, match="Factory creation failed", ):
            get_database_resources(TEST_DATABASE_URL)

    mock_engine.dispose.assert_called_once()


def test_dispose_database_resources_disposes_all_engines():
    mock_engine_1 = MagicMock(spec=Engine)
    mock_engine_2 = MagicMock(spec=Engine)

    with (
        patch(
            "app.db.session.create_database_engine",
            side_effect=[mock_engine_1, mock_engine_2],
        ),
        patch(
            "app.db.session.create_session_factory",
            side_effect=[MagicMock(), MagicMock()],
        ),
    ):
        get_database_resources(TEST_DATABASE_URL)
        get_database_resources(SECOND_DATABASE_URL)

        dispose_database_resources()

    mock_engine_1.dispose.assert_called_once()
    mock_engine_2.dispose.assert_called_once()

def test_dispose_database_resources_allows_reinitialization():
    engine_1, factory_1 = get_database_resources(
        TEST_DATABASE_URL
    )

    dispose_database_resources()

    engine_2, factory_2 = get_database_resources(
        TEST_DATABASE_URL
    )

    assert engine_1 is not engine_2
    assert factory_1 is not factory_2


def test_get_db_session_yields_session_without_disposing_engine():
    mock_engine = MagicMock(spec=Engine)
    mock_session = MagicMock(spec=Session)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_session

    mock_session_factory = MagicMock(
        return_value=mock_context_manager
    )

    with (
        patch(
            "app.db.session.get_database_url",
            return_value=TEST_DATABASE_URL,
        ),
        patch(
            "app.db.session.get_database_resources",
            return_value=(mock_engine, mock_session_factory),
        ) as mock_get_resources,
    ):
        session_generator = get_db_session()

        session = next(session_generator)

        assert session is mock_session

        with pytest.raises(StopIteration):
            next(session_generator)

        mock_get_resources.assert_called_once_with(
            TEST_DATABASE_URL
        )

        mock_context_manager.__exit__.assert_called_once()
        mock_engine.dispose.assert_not_called()


@pytest.fixture
def cached_resources():
    engines = [MagicMock(spec=Engine), MagicMock(spec=Engine)]
    factories = [MagicMock(), MagicMock()]
    with (
        patch("app.db.session.create_database_engine", side_effect=engines) as create_engine,
        patch("app.db.session.create_session_factory", side_effect=factories) as create_factory,
    ):
        for url in (TEST_DATABASE_URL, SECOND_DATABASE_URL):
            get_database_resources(url)
        try:
            yield SimpleNamespace(
                engines=engines, factories=factories,
                create_engine=create_engine, create_factory=create_factory,
            )
        finally:
            # Recover through the public cleanup API, without resetting globals.
            for engine in engines:
                engine.dispose.side_effect = None
            dispose_database_resources()


def test_successful_disposal_removes_all_cached_entries(cached_resources):
    dispose_database_resources()
    for engine in cached_resources.engines:
        engine.dispose.assert_called_once_with()
    assert session_module._database_resources == {}
    assert session_module._database_disposal_failed is False


@pytest.mark.parametrize("failed_index", [0, 1])
def test_disposal_attempts_every_engine_and_retains_only_failed_resources(
        cached_resources, failed_index,
):
    error = RuntimeError("disposal failed")
    failed_engine = cached_resources.engines[failed_index]
    failed_factory = cached_resources.factories[failed_index]
    failed_url = (TEST_DATABASE_URL, SECOND_DATABASE_URL)[failed_index]
    failed_engine.dispose.side_effect = error

    with pytest.raises(RuntimeError) as caught:
        dispose_database_resources()

    assert caught.value is error
    for engine in cached_resources.engines:
        engine.dispose.assert_called_once_with()
    assert list(session_module._database_resources) == [failed_url]
    engine, factory = session_module._database_resources[failed_url]
    assert engine is failed_engine
    assert factory is failed_factory
    assert session_module._database_disposal_failed is True


def test_disposal_failure_blocks_existing_and_new_urls_without_creating_resources(cached_resources):
    cached_resources.engines[0].dispose.side_effect = RuntimeError("disposal failed")
    with pytest.raises(RuntimeError, match="disposal failed"):
        dispose_database_resources()
    cached_resources.create_engine.reset_mock()
    cached_resources.create_factory.reset_mock()

    for url in (TEST_DATABASE_URL, SECOND_DATABASE_URL, TEST_DATABASE_URL + "_new"):
        with pytest.raises(RuntimeError, match="disposal previously failed"):
            get_database_resources(url)

    cached_resources.create_engine.assert_not_called()
    cached_resources.create_factory.assert_not_called()


def test_repeated_failure_preserves_resources_until_successful_recovery(cached_resources):
    engine, factory = cached_resources.engines[0], cached_resources.factories[0]
    errors = [RuntimeError("first failure"), RuntimeError("retry failure")]
    engine.dispose.side_effect = errors

    for error in errors:
        with pytest.raises(RuntimeError) as caught:
            dispose_database_resources()
        assert caught.value is error
        assert session_module._database_disposal_failed is True
        retained = session_module._database_resources[TEST_DATABASE_URL]
        assert retained[0] is engine
        assert retained[1] is factory

    assert engine.dispose.call_count == 2
    cached_resources.engines[1].dispose.assert_called_once_with()
    engine.dispose.side_effect = None
    dispose_database_resources()
    assert engine.dispose.call_count == 3
    assert session_module._database_resources == {}
    assert session_module._database_disposal_failed is False

    new_engine, new_factory = MagicMock(spec=Engine), MagicMock()
    with (
        patch("app.db.session.create_database_engine", return_value=new_engine) as create_engine,
        patch("app.db.session.create_session_factory", return_value=new_factory) as create_factory,
    ):
        recovered_engine, recovered_factory = get_database_resources(TEST_DATABASE_URL)
    assert recovered_engine is new_engine
    assert recovered_factory is new_factory
    assert recovered_engine is not engine
    assert recovered_factory is not factory
    create_engine.assert_called_once_with(TEST_DATABASE_URL)
    create_factory.assert_called_once_with(new_engine)


@pytest.mark.parametrize("multiple", [False, True])
def test_disposal_errors_preserve_identity_and_are_raised_after_unlock(cached_resources, multiple):
    errors = [RuntimeError("first failure")]
    if multiple:
        errors.append(KeyboardInterrupt("second failure"))
    for engine, error in zip(cached_resources.engines, errors):
        engine.dispose.side_effect = error

    with pytest.raises(BaseExceptionGroup if multiple else RuntimeError) as caught:
        dispose_database_resources()

    acquired = session_module._database_resources_lock.acquire(blocking=False)
    try:
        assert acquired, "Disposal raised while still holding the resource lock"
    finally:
        if acquired:
            session_module._database_resources_lock.release()
    if multiple:
        assert caught.value.exceptions == tuple(errors)
        assert all(actual is expected for actual, expected in zip(caught.value.exceptions, errors))
        assert len(session_module._database_resources) == 2
    else:
        assert caught.value is errors[0]


def test_resource_request_waiting_during_failed_disposal_is_rejected(cached_resources):
    entered, finish, requested, completed = Event(), Event(), Event(), Event()
    disposal_error = RuntimeError("disposal failed")
    disposal_errors: list[BaseException] = []
    request_errors: list[BaseException] = []
    results = []

    def fail_disposal():
        entered.set()
        if not finish.wait(timeout=5):
            raise RuntimeError("Test did not release disposal")
        raise disposal_error

    def dispose():
        try:
            dispose_database_resources()
        except BaseException as exc:
            disposal_errors.append(exc)

    def request():
        requested.set()
        try:
            results.append(get_database_resources(TEST_DATABASE_URL))
        except BaseException as exc:
            request_errors.append(exc)
        finally:
            completed.set()

    cached_resources.engines[0].dispose.side_effect = fail_disposal
    cached_resources.create_engine.reset_mock()
    cached_resources.create_factory.reset_mock()
    disposer, requester = Thread(target=dispose), Thread(target=request)
    disposer.start()
    try:
        assert entered.wait(timeout=2)
        requester.start()
        assert requested.wait(timeout=2)
        assert not completed.wait(timeout=0.1), "Resource request bypassed the disposal lock"
    finally:
        finish.set()
        disposer.join(timeout=5)
        if requester.ident is not None:
            requester.join(timeout=5)
    assert not disposer.is_alive()
    assert not requester.is_alive()
    assert disposal_errors == [disposal_error]
    assert results == []
    assert len(request_errors) == 1
    assert isinstance(request_errors[0], RuntimeError)
    assert "disposal previously failed" in str(request_errors[0])
    cached_resources.create_engine.assert_not_called()
    cached_resources.create_factory.assert_not_called()


def test_get_db_session_closes_session_when_request_fails():
    mock_engine = MagicMock(spec=Engine)
    mock_session = MagicMock(spec=Session)

    mock_context_manager = MagicMock()
    mock_context_manager.__enter__.return_value = mock_session

    mock_session_factory = MagicMock(
        return_value=mock_context_manager
    )

    with (
        patch(
            "app.db.session.get_database_url",
            return_value=TEST_DATABASE_URL,
        ),
        patch(
            "app.db.session.get_database_resources",
            return_value=(mock_engine, mock_session_factory),
        ),
    ):
        session_generator = get_db_session()

        next(session_generator)

        with pytest.raises(
                RuntimeError,
                match="Request failed",
        ):
            session_generator.throw(
                RuntimeError("Request failed")
            )

        mock_context_manager.__exit__.assert_called_once()
        mock_engine.dispose.assert_not_called()
