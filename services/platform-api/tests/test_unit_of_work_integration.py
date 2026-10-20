
from collections.abc import Iterator
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.db.models.application import ApplicationModel
from app.db.session import create_database_engine, get_database_url
from app.db.unit_of_work import UnitOfWork
from app.domain.application import Application, ApplicationStatus
from app.repositories.postgres_application_repository import (
    PostgresApplicationRepository,
)


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
def repository(
        db_session: Session,
) -> PostgresApplicationRepository:
    return PostgresApplicationRepository(db_session)


@pytest.fixture
def application() -> Application:
    return Application(
        id=uuid4(),
        name="unit-of-work-integration-app",
        repository_url="https://gitlab.com/example/uow-integration",
        status=ApplicationStatus.REGISTERED,
    )


def test_commit_persists_application_within_outer_transaction(
        repository: PostgresApplicationRepository,
        db_session: Session,
        connection: Connection,
        application: Application,
) -> None:
    with UnitOfWork(db_session) as uow:
        repository.save(application)
        uow.commit()

    # Read using the connection that owns the outer transaction.
    statement = select(ApplicationModel).where(
        ApplicationModel.id == application.id
    )

    stored_model = connection.execute(statement).first()

    assert stored_model is not None


def test_exit_without_commit_rolls_back(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    with UnitOfWork(db_session):
        repository.save(application)

    assert repository.get_by_id(application.id) is None


def test_exception_rolls_back(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    with pytest.raises(RuntimeError, match="Simulated failure"):
        with UnitOfWork(db_session):
            repository.save(application)
            raise RuntimeError("Simulated failure")

    assert repository.get_by_id(application.id) is None


def test_explicit_rollback_removes_application(
        repository: PostgresApplicationRepository,
        db_session: Session,
        application: Application,
) -> None:
    with UnitOfWork(db_session) as uow:
        repository.save(application)
        uow.rollback()

    assert repository.get_by_id(application.id) is None


def test_multiple_operations_commit_together(
        repository: PostgresApplicationRepository,
        db_session: Session,
) -> None:
    first_application = Application(
        id=uuid4(),
        name="first-uow-app",
        repository_url="https://gitlab.com/example/first",
        status=ApplicationStatus.REGISTERED,
    )

    second_application = Application(
        id=uuid4(),
        name="second-uow-app",
        repository_url="https://gitlab.com/example/second",
        status=ApplicationStatus.REGISTERED,
    )

    with UnitOfWork(db_session) as uow:
        repository.save(first_application)
        repository.save(second_application)
        uow.commit()

    assert repository.get_by_id(first_application.id) == first_application
    assert repository.get_by_id(second_application.id) == second_application


def test_multiple_operations_roll_back_together(
        repository: PostgresApplicationRepository,
        db_session: Session,
) -> None:
    first_application = Application(
        id=uuid4(),
        name="rollback-first-app",
        repository_url="https://gitlab.com/example/rollback-first",
        status=ApplicationStatus.REGISTERED,
    )

    second_application = Application(
        id=uuid4(),
        name="rollback-second-app",
        repository_url="https://gitlab.com/example/rollback-second",
        status=ApplicationStatus.REGISTERED,
    )

    with UnitOfWork(db_session):
        repository.save(first_application)
        repository.save(second_application)

    assert repository.get_by_id(first_application.id) is None
    assert repository.get_by_id(second_application.id) is None
