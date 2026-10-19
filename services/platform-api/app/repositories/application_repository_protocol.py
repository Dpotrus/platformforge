from typing import Protocol
from uuid import UUID

from app.domain.application import Application


class ApplicationRepositoryProtocol(Protocol):

    def save(self, application: Application) -> Application:
        ...

    def list_all(self) -> list[Application]:
        ...

    def get_by_id(self,application_id: UUID) -> Application | None:
        ...