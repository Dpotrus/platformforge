from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

from app.domain.application import ApplicationStatus


class ApplicationCreate(BaseModel):
    name: str = Field(
        min_length=3,
        max_length=100,
        description="Name of the application",
    )

    repository_url: HttpUrl


class ApplicationResponse(BaseModel):
    id: UUID
    name: str
    repository_url: HttpUrl
    status: ApplicationStatus
