from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.application import ApplicationModel
from app.db.session import get_database_url, create_database_engine, create_session_factory
from app.domain.application import Application, ApplicationStatus
from app.repositories.postgres_application_repository import PostgresApplicationRepository


@pytest.fixture
def db_session() -> Iterator[Session]:
    database_url = get_database_url()

    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    session = session_factory()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()

@pytest.fixture
def repository(
        db_session: Session,
) -> PostgresApplicationRepository:
    return PostgresApplicationRepository(db_session)

@pytest.fixture
def application() -> Application:
    return Application(
        id=uuid4(),
        name="integration-test-app",
        repository_url="https://gitlab.com/example/integration-test-app",
        status=ApplicationStatus.REGISTERED,
    )

def test_save_persists_application_within_transaction(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    saved_application = repository.save(application)

    stored_model = db_session.get(
        ApplicationModel,
        application.id,
    )

    assert saved_application == application
    assert stored_model is not None
    assert stored_model.id == application.id
    assert stored_model.name == application.name
    assert stored_model.repository_url == application.repository_url
    assert stored_model.status == ApplicationStatus.REGISTERED

def test_get_by_id_returns_saved_application(
        repository: PostgresApplicationRepository,
        application: Application,
) -> None:
    repository.save(application)

    result = repository.get_by_id(application.id)

    assert result == application


def test_get_by_id_returns_none_for_unknown_id(
        repository: PostgresApplicationRepository,
) -> None:
    result = repository.get_by_id(uuid4())

    assert result is None

def test_list_all_includes_saved_application(
        repository: PostgresApplicationRepository,
        application: Application,
) -> None:
    repository.save(application)

    results = repository.list_all()

    assert application in results

def test_list_all_orders_applications_by_name(
        repository: PostgresApplicationRepository,
) -> None:
    application_z = Application(
        id=uuid4(),
        name="zzz-integration-app",
        repository_url="https://gitlab.com/example/zzz",
        status=ApplicationStatus.REGISTERED,
    )

    application_a = Application(
        id=uuid4(),
        name="aaa-integration-app",
        repository_url="https://gitlab.com/example/aaa",
        status=ApplicationStatus.REGISTERED,
    )

    repository.save(application_z)
    repository.save(application_a)

    results = repository.list_all()

    names = [application.name for application in results]

    assert names == sorted(names)

def test_save_does_not_commit_transaction(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    repository.save(application)

    assert db_session.in_transaction()

    with db_session.get_bind().connect() as other_connection:
        statement = select(ApplicationModel).where(
            ApplicationModel.id == application.id
        )

        result = other_connection.execute(statement).first()

        assert result is None

def test_rollback_removes_uncommitted_application(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    repository.save(application)

    assert db_session.get(ApplicationModel, application.id) is not None

    db_session.rollback()

    assert db_session.get(ApplicationModel, application.id) is None