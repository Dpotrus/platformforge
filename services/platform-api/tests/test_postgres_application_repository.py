from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.models.application import ApplicationModel
from app.domain.application import Application, ApplicationStatus
from app.repositories.postgres_application_repository import PostgresApplicationRepository


@pytest.fixture
def session() -> Mock:
    return Mock(spec=Session)

@pytest.fixture
def repository(session: Mock) -> PostgresApplicationRepository:
    return PostgresApplicationRepository(session)


@pytest.fixture
def application() -> Application:
    return Application(
        id=uuid4(),
        name="platformforge-api",
        repository_url="https://gitlab.com/example/platformforge",
        status=ApplicationStatus.REGISTERED,
    )

def test_save_adds_correct_model(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    result = repository.save(application)

    session.add.assert_called_once()

    model = session.add.call_args.args[0]

    assert isinstance(model, ApplicationModel)
    assert model.id == application.id
    assert model.name == application.name
    assert model.repository_url == application.repository_url
    assert model.status == application.status

    assert result == application


def test_save_flushes_session(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    repository.save(application)

    session.flush.assert_called_once_with()

def test_save_does_not_commit(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    repository.save(application)

    session.commit.assert_not_called()

def test_save_propagates_flush_error(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    session.flush.side_effect = RuntimeError("Database write failed")

    with pytest.raises(RuntimeError, match="Database write failed"):
        repository.save(application)

    session.commit.assert_not_called()

def test_list_all_returns_domain_applications(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    model = ApplicationModel(
        id=application.id,
        name=application.name,
        repository_url=application.repository_url,
        status=application.status,
    )

    session.scalars.return_value.all.return_value = [model]

    result = repository.list_all()

    assert result == [application]
    assert isinstance(result[0], Application)
    session.scalars.assert_called_once()

def test_list_all_returns_empty_list(
        repository: PostgresApplicationRepository,
        session: Mock,
) -> None:
    session.scalars.return_value.all.return_value = []

    result = repository.list_all()

    assert result == []
    session.scalars.assert_called_once()

def test_list_all_orders_by_name(
        repository: PostgresApplicationRepository,
        session: Mock,
) -> None:
    session.scalars.return_value.all.return_value = []

    repository.list_all()

    statement = session.scalars.call_args.args[0]

    assert "ORDER BY applications.name" in str(statement)

def test_get_by_id_returns_domain_application(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    model = ApplicationModel(
        id=application.id,
        name=application.name,
        repository_url=application.repository_url,
        status=application.status,
    )

    session.get.return_value = model

    result = repository.get_by_id(application.id)

    assert result == application
    assert isinstance(result, Application)
    session.get.assert_called_once_with(
        ApplicationModel,
        application.id,
    )

def test_get_by_id_returns_none_when_not_found(
        repository: PostgresApplicationRepository,
        session: Mock,
) -> None:
    application_id = uuid4()
    session.get.return_value = None

    result = repository.get_by_id(application_id)

    assert result is None
    session.get.assert_called_once_with(
        ApplicationModel,
        application_id,
    )

def test_repository_does_not_close_session(
        repository: PostgresApplicationRepository,
        session: Mock,
        application: Application,
) -> None:
    session.scalars.return_value.all.return_value = []
    session.get.return_value = None

    repository.save(application)
    repository.list_all()
    repository.get_by_id(application.id)

    session.close.assert_not_called()