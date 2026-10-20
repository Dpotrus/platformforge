from uuid import uuid4

from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.db.unit_of_work import UnitOfWork
from app.domain.application import Application, ApplicationStatus
from app.exceptions import ApplicationStorageUnavailable, ApplicationStorageError
from app.repositories.application_repository_protocol import ApplicationRepositoryProtocol


class ApplicationService:

    def __init__(self, repository: ApplicationRepositoryProtocol, unit_of_work: UnitOfWork | None = None) -> None:
        self._repository = repository
        self._unit_of_work = unit_of_work

    def list_applications(self) -> list[Application]:
        try:
            return self._repository.list_all()
        except OperationalError as exc:
            raise ApplicationStorageUnavailable(
                "Application storage is unavailable"
            ) from exc
        except SQLAlchemyError as exc:
            raise ApplicationStorageError(
                "Failed to list applications"
            ) from exc

    def create_application(self, name: str, repository_url: str) -> Application:
        new_application = Application(id=uuid4(),
                                      name=name,
                                      repository_url=repository_url,
                                      status=ApplicationStatus.REGISTERED,
                                      )
        try:

            if self._unit_of_work is None:
                return self._repository.save(new_application)

            with self._unit_of_work as uow:
                saved_application = self._repository.save(new_application)
                uow.commit()
                return saved_application
        except OperationalError as exc:
            raise ApplicationStorageUnavailable(
                "Application storage is unavailable"
            ) from exc
        except SQLAlchemyError as exc:
            raise ApplicationStorageError(
                "Failed to create application"
            ) from exc