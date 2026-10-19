
from dataclasses import FrozenInstanceError
from uuid import UUID, uuid4

import pytest

from app.domain.application import Application, ApplicationStatus


@pytest.fixture
def valid_application_data() -> dict:
    return {
        "id": uuid4(),
        "name": "payment-service",
        "repository_url": "https://github.com/example/payment-service",
        "status": ApplicationStatus.REGISTERED,
    }


def test_create_valid_application(valid_application_data: dict):
    application = Application(**valid_application_data)

    assert isinstance(application.id, UUID)
    assert application.name == "payment-service"
    assert application.repository_url == (
        "https://github.com/example/payment-service"
    )
    assert application.status is ApplicationStatus.REGISTERED


@pytest.mark.parametrize(
    "name",
    [
        "",
        "ab",
        "a" * 101,
        None,
        123,
        ],
)
def test_reject_invalid_application_name(
        valid_application_data: dict,
        name,
):
    valid_application_data["name"] = name

    with pytest.raises(ValueError):
        Application(**valid_application_data)


@pytest.mark.parametrize(
    "name",
    [
        "abc",
        "a" * 100,
        ],
)
def test_accept_valid_application_name_boundaries(
        valid_application_data: dict,
        name: str,
):
    valid_application_data["name"] = name

    application = Application(**valid_application_data)

    assert application.name == name


@pytest.mark.parametrize(
    "repository_url",
    [
        "",
        "invalid-url",
        "ftp://github.com/example/repository",
        "https://",
        "https://github.com:invalid/repository",
        "https://github.com/invalid path",
        None,
        123,
    ],
)
def test_reject_invalid_repository_url(
        valid_application_data: dict,
        repository_url,
):
    valid_application_data["repository_url"] = repository_url

    with pytest.raises(ValueError):
        Application(**valid_application_data)


@pytest.mark.parametrize(
    "repository_url",
    [
        "https://github.com/example/payment-service",
        "http://gitlab.example.com/team/project",
    ],
)
def test_accept_valid_repository_url(
        valid_application_data: dict,
        repository_url: str,
):
    valid_application_data["repository_url"] = repository_url

    application = Application(**valid_application_data)

    assert application.repository_url == repository_url


@pytest.mark.parametrize(
    "application_id",
    [
        "not-a-uuid",
        None,
        123,
    ],
)
def test_reject_invalid_application_id(
        valid_application_data: dict,
        application_id,
):
    valid_application_data["id"] = application_id

    with pytest.raises(ValueError, match="Application id must be a UUID"):
        Application(**valid_application_data)


@pytest.mark.parametrize(
    "application_status",
    [
        "registered",
        "unknown",
        None,
        123,
    ],
)
def test_reject_invalid_application_status(
        valid_application_data: dict,
        application_status,
):
    valid_application_data["status"] = application_status

    with pytest.raises(ValueError, match="Invalid application status"):
        Application(**valid_application_data)


def test_application_is_immutable(valid_application_data: dict):
    application = Application(**valid_application_data)

    with pytest.raises(FrozenInstanceError):
        application.name = "another-service"
