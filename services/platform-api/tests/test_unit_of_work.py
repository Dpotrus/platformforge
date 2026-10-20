
from unittest.mock import Mock

import pytest
from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork


@pytest.fixture
def session() -> Mock:
    return Mock(spec=Session)


@pytest.fixture
def unit_of_work(session: Mock) -> UnitOfWork:
    return UnitOfWork(session)


def test_commit_calls_session_commit(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with unit_of_work as uow:
        uow.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_not_called()


def test_exit_without_commit_rolls_back(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with unit_of_work:
        pass

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_exception_rolls_back_transaction(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with pytest.raises(ValueError, match="Simulated failure"):
        with unit_of_work:
            raise ValueError("Simulated failure")

    session.rollback.assert_called_once_with()
    session.commit.assert_not_called()


def test_exception_is_not_suppressed(
        unit_of_work: UnitOfWork,
) -> None:
    with pytest.raises(RuntimeError, match="Operation failed"):
        with unit_of_work:
            raise RuntimeError("Operation failed")


def test_explicit_rollback_calls_session_rollback(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    unit_of_work.rollback()

    session.rollback.assert_called_once_with()


def test_explicit_rollback_prevents_commit_state(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with unit_of_work as uow:
        uow.commit()
        uow.rollback()

    session.commit.assert_called_once_with()
    assert session.rollback.call_count == 2


def test_failed_commit_triggers_rollback(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    session.commit.side_effect = RuntimeError("Commit failed")

    with pytest.raises(RuntimeError, match="Commit failed"):
        with unit_of_work as uow:
            uow.commit()

    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()


def test_unit_of_work_does_not_close_session(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with unit_of_work as uow:
        uow.commit()

    session.close.assert_not_called()


def test_enter_returns_same_instance(
        unit_of_work: UnitOfWork,
) -> None:
    with unit_of_work as uow:
        assert uow is unit_of_work


def test_new_context_resets_commit_state(
        unit_of_work: UnitOfWork,
        session: Mock,
) -> None:
    with unit_of_work as uow:
        uow.commit()

    with unit_of_work:
        pass

    session.commit.assert_called_once_with()
    session.rollback.assert_called_once_with()
