from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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