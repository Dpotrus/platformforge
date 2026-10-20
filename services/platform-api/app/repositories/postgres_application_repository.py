from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.application import ApplicationModel
from app.domain.application import Application


class PostgresApplicationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def save(self, application: Application) -> Application:
        model = ApplicationModel(
            id=application.id,
            name=application.name,
            repository_url=application.repository_url,
            status=application.status,
        )

        self._session.add(model)
        self._session.flush()

        return application
    def list_all(self) -> list[Application]:
        statement = select(ApplicationModel).order_by(ApplicationModel.name)

        models = self._session.scalars(statement).all()

        return [self._to_domain(model) for model in models]

    def get_by_id(self, application_id: UUID) -> Application | None:
        model = self._session.get(ApplicationModel, application_id)

        if model is None:
            return None

        return self._to_domain(model)

    @staticmethod
    def _to_domain(model: ApplicationModel) -> Application:
        return Application(
            id=model.id,
            name=model.name,
            repository_url=model.repository_url,
            status=model.status,
        )