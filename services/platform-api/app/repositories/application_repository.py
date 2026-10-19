from uuid import UUID

from app.domain.application import Application


class ApplicationRepository:
    def __init__(self) -> None:
        self._applications: dict[UUID, Application] = {}

    def save(self, application: Application) -> Application:
        self._applications[application.id] = application
        return application

    def list_all(self) -> list[Application]:
        return list(self._applications.values())

    def get_by_id(self, application_id: UUID) -> Application | None:
        return self._applications.get(application_id)