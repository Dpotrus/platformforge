
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.db.models.application import ApplicationModel
from app.db.session import create_database_engine, get_database_url, get_db_session
from app.main import app


@pytest.fixture
def engine() -> Iterator[Engine]:
    database_engine = create_database_engine(get_database_url())

    try:
        yield database_engine
    finally:
        database_engine.dispose()


@pytest.fixture
def connection(engine: Engine) -> Iterator[Connection]:
    with engine.connect() as database_connection:
        transaction = database_connection.begin()

        try:
            yield database_connection
        finally:
            if transaction.is_active:
                transaction.rollback()


@pytest.fixture
def db_session(connection: Connection) -> Iterator[Session]:
    session = Session(
        bind=connection,
        autoflush=False,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session) -> Iterator[TestClient]:
    def override_get_db_session() -> Iterator[Session]:
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_db_session

    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_db_session, None)

def test_post_creates_application(client: TestClient) -> None:
    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "api-integration-app",
            "repository_url": "https://gitlab.com/example/api-integration",
        },
    )

    assert response.status_code == 201

    body = response.json()

    assert body["name"] == "api-integration-app"
    assert body["status"] == "registered"
    assert "id" in body

def test_get_returns_created_application(client: TestClient) -> None:
    create_response = client.post(
        "/api/v1/applications/",
        json={
            "name": "get-integration-app",
            "repository_url": "https://gitlab.com/example/get-integration",
        },
    )

    assert create_response.status_code == 201

    application_id = create_response.json()["id"]

    response = client.get("/api/v1/applications/")

    assert response.status_code == 200

    applications = response.json()

    assert any(
        application["id"] == application_id
        for application in applications
    )

def test_post_persists_application_in_database(
        client: TestClient,
        connection: Connection,
) -> None:
    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "persisted-api-app",
            "repository_url": "https://gitlab.com/example/persisted",
        },
    )

    assert response.status_code == 201

    application_id = response.json()["id"]

    statement = select(ApplicationModel).where(
        ApplicationModel.id == application_id
    )

    row = connection.execute(statement).first()

    assert row is not None


def test_invalid_application_returns_422(client: TestClient) -> None:
    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "ab",
            "repository_url": "not-a-valid-url",
        },
    )

    assert response.status_code == 422

def test_multiple_posts_persist_both_applications(
        client: TestClient,
) -> None:
    first_response = client.post(
        "/api/v1/applications/",
        json={
            "name": "first-api-app",
            "repository_url": "https://gitlab.com/example/first-api",
        },
    )

    second_response = client.post(
        "/api/v1/applications/",
        json={
            "name": "second-api-app",
            "repository_url": "https://gitlab.com/example/second-api",
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201

    response = client.get("/api/v1/applications/")

    application_ids = {
        application["id"]
        for application in response.json()
    }

    assert first_response.json()["id"] in application_ids
    assert second_response.json()["id"] in application_ids

def test_dependency_injection_uses_shared_session(
        client: TestClient,
        db_session: Session,
) -> None:
    response = client.post(
        "/api/v1/applications/",
        json={
            "name": "shared-session-app",
            "repository_url": "https://gitlab.com/example/shared-session",
        },
    )

    assert response.status_code == 201

    application_id = response.json()["id"]

    model = db_session.get(ApplicationModel, application_id)

    assert model is not None
    assert model.name == "shared-session-app"