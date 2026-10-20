from typing import Annotated

from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db_session
from app.db.unit_of_work import UnitOfWork
from app.domain.application import Application
from app.repositories.postgres_application_repository import PostgresApplicationRepository
from app.schemas.application import ApplicationResponse, ApplicationCreate
from app.services.application_service import ApplicationService

router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)


def get_application_repository(session: Annotated[Session, Depends(get_db_session)]) -> PostgresApplicationRepository:
    return PostgresApplicationRepository(session)


def get_application_service(repository: Annotated[PostgresApplicationRepository, Depends(get_application_repository)],
                            session: Annotated[Session, Depends(get_db_session)]) -> ApplicationService:
    return ApplicationService(repository=repository, unit_of_work=UnitOfWork(session))


def to_application_response(application: Application) -> ApplicationResponse:
    return ApplicationResponse(
        id=application.id,
        name=application.name,
        repository_url=application.repository_url,
        status=application.status
    )


@router.get("/", response_model=list[ApplicationResponse])
def list_applications(application_service: Annotated[ApplicationService, Depends(get_application_service)]) -> list[ApplicationResponse]:
    applications = application_service.list_applications()
    return [to_application_response(application) for application in applications]


@router.post("/", response_model=ApplicationResponse, status_code=status.HTTP_201_CREATED)
def create_application(application: ApplicationCreate, application_service: Annotated[ApplicationService, Depends(get_application_service)]) -> ApplicationResponse:
    try:
        created_application = application_service.create_application(application.name, str(application.repository_url))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return to_application_response(created_application)
