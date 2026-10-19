from uuid import uuid4

import pytest

from app.domain.application import Application, ApplicationStatus
from app.repositories.application_repository import ApplicationRepository

@pytest.fixture
def repository() -> ApplicationRepository:
    return ApplicationRepository()

@pytest.fixture
def application() -> Application:
    return Application(
        id=uuid4(),
        name="payment-service",
        repository_url="https://github.com/example/payment-service",
        status=ApplicationStatus.REGISTERED,
    )


def test_save_application(repository: ApplicationRepository,
                          application: Application):

    saved_application = repository.save(application)

    assert saved_application == application
    assert isinstance(saved_application, Application)
    assert len(repository.list_all()) == 1

def test_list_all_applications(repository: ApplicationRepository,
                               application: Application):

    repository.save(application)

    applications = repository.list_all()

    assert len(applications) == 1
    assert applications[0] == application
    assert isinstance(applications[0], Application)


def test_get_application_by_id(repository: ApplicationRepository,
                               application: Application):
    repository.save(application)

    found_application = repository.get_by_id(application.id)

    assert found_application == application
    assert isinstance(found_application, Application)
    assert found_application.status is ApplicationStatus.REGISTERED


def test_get_application_by_id_returns_none(repository: ApplicationRepository):

    unknown_id = uuid4()

    found_application = repository.get_by_id(unknown_id)

    assert found_application is None