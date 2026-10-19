from uuid import UUID

import pytest

from app.domain.application import Application, ApplicationStatus
from app.repositories.application_repository import ApplicationRepository
from app.services.application_service import ApplicationService


@pytest.fixture
def service() -> ApplicationService:
    repository = ApplicationRepository()
    return ApplicationService(repository)

def test_list_applications_returns_empty_list(service: ApplicationService):
    applications = service.list_applications()

    assert applications == []

def test_create_application_returns_registered_application(service: ApplicationService):
    created_application = service.create_application(
        name="payment-service",
        repository_url="https://github.com/example/payment-service",
    )

    assert isinstance(created_application, Application)
    assert isinstance(created_application.id, UUID)

    assert created_application.name == "payment-service"
    assert created_application.repository_url == (
        "https://github.com/example/payment-service"
    )
    assert created_application.status is ApplicationStatus.REGISTERED


def test_list_applications_returns_created_application(service: ApplicationService):
    created_application = service.create_application(
        name="payment-service",
        repository_url="https://github.com/example/payment-service",
    )

    applications = service.list_applications()

    assert len(applications) == 1
    assert applications[0] == created_application
    assert isinstance(applications[0], Application)