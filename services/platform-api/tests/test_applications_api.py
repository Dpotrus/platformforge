from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api.v1.applications import get_application_repository, get_application_service
from app.main import app
from app.repositories.application_repository import ApplicationRepository


@pytest.fixture
def client():
    repository = ApplicationRepository()

    def override_repository() -> ApplicationRepository:
        return repository

    app.dependency_overrides[get_application_repository] = override_repository

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_application_repository, None)


def test_create_application_returns_201(client: TestClient):
    payload = {
        "name": "payment-service",
        "repository_url": "https://github.com/example/payment-service",
    }

    response = client.post(
        "/api/v1/applications/",
        json=payload,
    )

    assert response.status_code == 201

    data = response.json()

    assert UUID(data["id"])
    assert data["name"] == "payment-service"
    assert data["repository_url"] == (
        "https://github.com/example/payment-service"
    )
    assert data["status"] == "registered"


@pytest.mark.parametrize(
    "payload",
    [
        {
            "name": "ab",
            "repository_url": "https://github.com/example/payment-service",
        },
        {
            "name": "payment-service",
            "repository_url": "invalid-url",
        },
    ],
)
def test_create_application_returns_422_for_invalid_data(client: TestClient,
                                                         payload: dict[str, str]):
    response = client.post(
        "/api/v1/applications/",
        json=payload,
    )

    assert response.status_code == 422

    data = response.json()

    assert "detail" in data
    assert len(data["detail"]) > 0


def test_list_applications_returns_200(client: TestClient):
    response = client.get("/api/v1/applications/")

    assert response.status_code == 200
    assert response.json() == []


def test_create_application_can_be_listed(client: TestClient):
    payload = {
        "name": "inventory-service",
        "repository_url": "https://github.com/example/inventory-service",
    }

    create_response = client.post(
        "/api/v1/applications/",
        json=payload,
    )

    assert create_response.status_code == 201

    created_application = create_response.json()

    list_response = client.get("/api/v1/applications/")

    assert list_response.status_code == 200

    applications = list_response.json()

    assert len(applications) == 1
    assert applications[0] == created_application


def test_create_application_returns_422_for_domain_error(client: TestClient):
    class FailingApplicationService:
        def create_application(self, name: str, repository_url: str):
            raise ValueError("Application name is not allowed")

    def override_service() -> FailingApplicationService:
        return FailingApplicationService()

    app.dependency_overrides[get_application_service] = override_service

    try:
        payload = {
            "name": "payment-service",
            "repository_url": "https://github.com/example/payment-service",
        }

        response = client.post(
            "/api/v1/applications/",
            json=payload,
        )

        assert response.status_code == 422
        assert response.json() == {
            "detail": "Application name is not allowed"
        }
    finally:
        app.dependency_overrides.pop(get_application_service, None)

def test_create_application_does_not_hide_unexpected_errors(client: TestClient):
    class FailingApplicationService:
        def create_application(self, name: str, repository_url: str):
            raise RuntimeError("Unexpected internal failure")

    def override_service() -> FailingApplicationService:
        return FailingApplicationService()

    app.dependency_overrides[get_application_service] = override_service

    try:
        payload = {
            "name": "payment-service",
            "repository_url": "https://github.com/example/payment-service",
        }

        with pytest.raises(RuntimeError,match="Unexpected internal failure"):
            client.post(
                "/api/v1/applications/",
                json=payload,
            )
    finally:
        app.dependency_overrides.pop(get_application_service, None)