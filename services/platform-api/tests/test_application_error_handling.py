
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.v1.applications import get_application_service
from app.db.unit_of_work import UnitOfWork
from app.exceptions import (
    ApplicationStorageError,
    ApplicationStorageUnavailable,
)
from app.main import app
from app.services.application_service import ApplicationService


def make_operational_error() -> OperationalError:
    return OperationalError(
        "SELECT * FROM applications",
        {},
        Exception("secret database connection details"),
    )


@pytest.fixture
def repository() -> Mock:
    return Mock()


@pytest.fixture
def service(repository: Mock) -> ApplicationService:
    return ApplicationService(repository=repository)


@pytest.fixture
def client(service: ApplicationService) -> Iterator[TestClient]:
    app.dependency_overrides[get_application_service] = lambda: service

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_application_service, None)


# ---------------------------------------------------------
# Service layer: database exceptions -> application errors
# ---------------------------------------------------------


def test_service_translates_operational_error_when_listing(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.list_all.side_effect = make_operational_error()

    with pytest.raises(ApplicationStorageUnavailable) as exc_info:
        service.list_applications()

    assert isinstance(exc_info.value.__cause__, OperationalError)


def test_service_translates_sqlalchemy_error_when_listing(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.list_all.side_effect = SQLAlchemyError(
        "secret database error"
    )

    with pytest.raises(ApplicationStorageError) as exc_info:
        service.list_applications()

    assert not isinstance(
        exc_info.value,
        ApplicationStorageUnavailable,
    )
    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)


def test_service_translates_operational_error_when_creating(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.save.side_effect = make_operational_error()

    with pytest.raises(ApplicationStorageUnavailable) as exc_info:
        service.create_application(
            name="payment-service",
            repository_url="https://github.com/example/payment-service",
        )

    assert isinstance(exc_info.value.__cause__, OperationalError)


def test_service_translates_sqlalchemy_error_when_creating(
        service: ApplicationService,
        repository: Mock,
) -> None:
    repository.save.side_effect = SQLAlchemyError(
        "secret database error"
    )

    with pytest.raises(ApplicationStorageError) as exc_info:
        service.create_application(
            name="payment-service",
            repository_url="https://github.com/example/payment-service",
        )

    assert not isinstance(
        exc_info.value,
        ApplicationStorageUnavailable,
    )
    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)


# ---------------------------------------------------------
# API layer: application errors -> HTTP responses
# ---------------------------------------------------------


def test_get_returns_503_when_storage_unavailable(
        client: TestClient,
        repository: Mock,
) -> None:
    repository.list_all.side_effect = make_operational_error()

    response = client.get("/api/v1/applications/")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service temporarily unavailable"
    }
    assert "secret database connection details" not in response.text


def test_get_returns_500_when_storage_fails(
        client: TestClient,
        repository: Mock,
) -> None:
    repository.list_all.side_effect = SQLAlchemyError(
        "secret database error"
    )

    response = client.get("/api/v1/applications/")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Database operation failed"
    }
    assert "secret database error" not in response.text


def test_post_returns_503_when_storage_unavailable(
        client: TestClient,
        repository: Mock,
) -> None:
    repository.save.side_effect = make_operational_error()

    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "payment-service",
            "repository_url": "https://github.com/example/payment-service",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Service temporarily unavailable"
    }
    assert "secret database connection details" not in response.text


def test_post_returns_500_when_storage_fails(
        client: TestClient,
        repository: Mock,
) -> None:
    repository.save.side_effect = SQLAlchemyError(
        "secret database error"
    )

    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "payment-service",
            "repository_url": "https://github.com/example/payment-service",
        },
    )

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Database operation failed"
    }
    assert "secret database error" not in response.text


# ---------------------------------------------------------
# UnitOfWork: errors during commit
# ---------------------------------------------------------


def test_service_translates_operational_error_during_commit(
        repository: Mock,
) -> None:
    session = Mock()
    session.commit.side_effect = make_operational_error()

    service = ApplicationService(
        repository=repository,
        unit_of_work=UnitOfWork(session),
    )

    with pytest.raises(ApplicationStorageUnavailable) as exc_info:
        service.create_application(
            name="payment-service",
            repository_url="https://github.com/example/payment-service",
        )

    assert isinstance(exc_info.value.__cause__, OperationalError)
    session.rollback.assert_called_once()


def test_service_translates_sqlalchemy_error_during_commit(
        repository: Mock,
) -> None:
    session = Mock()
    session.commit.side_effect = SQLAlchemyError(
        "secret database error"
    )

    service = ApplicationService(
        repository=repository,
        unit_of_work=UnitOfWork(session),
    )

    with pytest.raises(ApplicationStorageError) as exc_info:
        service.create_application(
            name="payment-service",
            repository_url="https://github.com/example/payment-service",
        )

    assert not isinstance(
        exc_info.value,
        ApplicationStorageUnavailable,
    )
    assert isinstance(exc_info.value.__cause__, SQLAlchemyError)
    session.rollback.assert_called_once()
