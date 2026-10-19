from unittest.mock import patch, MagicMock

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.db.session import get_database_url, create_database_engine, create_session_factory, get_db_session, \
    get_database_resources, dispose_database_resources

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
    dispose_database_resources()
    yield
    dispose_database_resources()


def test_get_database_url_returns_environment_variable():
    with patch.dict("os.environ", {"DATABASE_URL": TEST_DATABASE_URL}):
        assert get_database_url() == TEST_DATABASE_URL


def test_get_database_url_raises_when_missing():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is not set"):
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
def test_get_database_url_rejects_invalid_dialect(invalid_url: str):
    with patch.dict("os.environ", {"DATABASE_URL": invalid_url}):
        with pytest.raises(ValueError, match="DATABASE_URL must use the postgresql"):
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
