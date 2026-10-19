from uuid import uuid4

from app.domain.application import Application, ApplicationStatus
from app.repositories.application_repository_protocol import ApplicationRepositoryProtocol


class ApplicationService:

    def __init__(self, repository: ApplicationRepositoryProtocol) -> None:
        self._repository = repository

    def list_applications(self) -> list[Application]:
        return self._repository.list_all()

    def create_application(self, name: str, repository_url: str) -> Application:
        new_application = Application(id=uuid4(),
                                      name=name,
                                      repository_url=repository_url,
                                      status=ApplicationStatus.REGISTERED,
                                      )

        return self._repository.save(new_application)
