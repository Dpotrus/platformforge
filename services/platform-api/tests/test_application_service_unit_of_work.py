from unittest.mock import Mock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork
from app.domain.application import Application, ApplicationStatus
from app.repositories.application_repository import ApplicationRepository
from app.repositories.application_repository_protocol import (
    ApplicationRepositoryProtocol,
)
from app.services.application_service import ApplicationService

@pytest.fixture
def session() -> Mock:
    return Mock(spec=Session)


@pytest.fixture
def repository() -> Mock:
    return Mock(spec=ApplicationRepositoryProtocol)


@pytest.fixture
def service(
        repository: Mock,
        session: Mock,
) -> ApplicationService:
    return ApplicationService(
        repository=repository,
        unit_of_work=UnitOfWork(session),
    )

def test_successful_create_commits_transaction(
        service: ApplicationService,
        repository: Mock,
        session: Mock,
) -> None:
    repository.save.side_effect = lambda application: application

    result = service.create_application(
        name="platformforge-api",
        repository_url="https://gitlab.com/example/platformforge",
    )

    assert isinstance(result, Application)
    assert result.name == "platformforge-api"
    assert result.status == ApplicationStatus.REGISTERED

    repository.save.assert_called_once()
    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()

def test_repository_error_triggers_rollback(
        service: ApplicationService,
        repository: Mock,
        session: Mock,
) -> None:
    repository.save.side_effect = RuntimeError("Database write failed")

    with pytest.raises(RuntimeError, match="Database write failed"):
        service.create_application(
            name="platformforge-api",
            repository_url="https://gitlab.com/example/platformforge",
        )

    session.commit.assert_not_called()
    session.rollback.assert_called_once_with()

def test_commit_error_triggers_rollback(
        service: ApplicationService,
        repository: Mock,
        session: Mock,
) -> None:
    repository.save.side_effect = lambda application: application
    session.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        service.create_application(
            name="platformforge-api",
            repository_url="https://gitlab.com/example/platformforge",
        )

    repository.save.assert_called_once()
    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()

def test_in_memory_repository_works_without_unit_of_work() -> None:
    repository = ApplicationRepository()
    service = ApplicationService(repository)

    created = service.create_application(
        name="in-memory-app",
        repository_url="https://gitlab.com/example/in-memory",
    )

    assert repository.get_by_id(created.id) == created
    assert service.list_applications() == [created]

def test_list_applications_does_not_commit(
        service: ApplicationService,
        repository: Mock,
        session: Mock,
) -> None:
    application = Application(
        id=uuid4(),
        name="existing-app",
        repository_url="https://gitlab.com/example/existing",
        status=ApplicationStatus.REGISTERED,
    )

    repository.list_all.return_value = [application]

    result = service.list_applications()

    assert result == [application]
    repository.list_all.assert_called_once_with()
    session.commit.assert_not_called()
    session.rollback.assert_not_called()

def test_created_application_is_passed_to_repository(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.save.side_effect = lambda application: application

    result = service.create_application(
        name="new-application",
        repository_url="https://gitlab.com/example/new-application",
    )

    saved_application = repository.save.call_args.args[0]

    assert saved_application == result
    assert saved_application.id is not None
    assert saved_application.name == "new-application"
    assert saved_application.repository_url == (
        "https://gitlab.com/example/new-application"
    )
    assert saved_application.status == ApplicationStatus.REGISTERED

def test_repository_error_is_not_suppressed(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.save.side_effect = ValueError("Invalid application")

    with pytest.raises(ValueError, match="Invalid application"):
        service.create_application(
            name="platformforge-api",
            repository_url="https://gitlab.com/example/platformforge",
        )

def test_unit_of_work_does_not_close_session(
        service: ApplicationService,
        repository: Mock,
        session: Mock,
) -> None:
    repository.save.side_effect = lambda application: application

    service.create_application(
        name="platformforge-api",
        repository_url="https://gitlab.com/example/platformforge",
    )

    session.close.assert_not_called()