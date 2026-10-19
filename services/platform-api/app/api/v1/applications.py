from typing import Annotated

from fastapi import APIRouter, Depends, status, HTTPException

from app.domain.application import Application
from app.repositories.application_repository import ApplicationRepository
from app.schemas.application import ApplicationResponse, ApplicationCreate
from app.services.application_service import ApplicationService

router = APIRouter(
    prefix="/applications",
    tags=["Applications"],
)

_repository = ApplicationRepository()


def get_application_repository() -> ApplicationRepository:
    return _repository


def get_application_service(repository: Annotated[ApplicationRepository, Depends(get_application_repository)]) -> ApplicationService:
    return ApplicationService(repository)


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
