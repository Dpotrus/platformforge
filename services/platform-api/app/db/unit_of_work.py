
from types import TracebackType

from sqlalchemy.orm import Session


class UnitOfWork:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._committed = False

    def __enter__(self) -> "UnitOfWork":
        self._committed = False
        return self

    def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc_value: BaseException | None,
            traceback: TracebackType | None,
    ) -> None:
        if exc_type is not None or not self._committed:
            self._session.rollback()

    def commit(self) -> None:
        self._session.commit()
        self._committed = True

    def rollback(self) -> None:
        self._session.rollback()
        self._committed = False
