import logging

from typing import NoReturn

from app.exceptions import (
    ApplicationStorageError,
    ApplicationStorageUnavailable,
)

from collections.abc import Callable
from contextlib import AbstractContextManager

import grpc
from sqlalchemy.orm import Session

from app.db.unit_of_work import UnitOfWork
from app.domain.application import ApplicationStatus
from app.repositories.postgres_application_repository import (
    PostgresApplicationRepository,
)
from app.services.application_service import ApplicationService
from platformforge.v1 import applications_pb2
from platformforge.v1 import applications_pb2_grpc


def to_proto_status(status: ApplicationStatus) -> int:
    status_mapping = {
        ApplicationStatus.REGISTERED:
            applications_pb2.APPLICATION_STATUS_REGISTERED,
        ApplicationStatus.DEPLOYED:
            applications_pb2.APPLICATION_STATUS_DEPLOYED,
        ApplicationStatus.FAILED:
            applications_pb2.APPLICATION_STATUS_FAILED,
    }

    return status_mapping[status]

logger = logging.getLogger(__name__)


def abort_on_storage_error(
        context: grpc.ServicerContext,
        exc: ApplicationStorageError,
) -> NoReturn:
    if isinstance(exc, ApplicationStorageUnavailable):
        logger.error(
            "Application storage unavailable",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        context.abort(
            grpc.StatusCode.UNAVAILABLE,
            "Service temporarily unavailable",
        )
    else:
        logger.error(
            "Application storage operation failed",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        context.abort(
            grpc.StatusCode.INTERNAL,
            "Database operation failed",
        )

class ApplicationServiceServicer(
    applications_pb2_grpc.ApplicationServiceServicer
):
    def __init__(
            self,
            session_factory: Callable[[], AbstractContextManager[Session]],
    ) -> None:
        self._session_factory = session_factory

    def ListApplications(
            self,
            request: applications_pb2.ListApplicationsRequest,
            context: grpc.ServicerContext,
    ) -> applications_pb2.ListApplicationsResponse:
        with self._session_factory() as session:
            repository = PostgresApplicationRepository(session)
            application_service = ApplicationService(
                repository=repository,
                unit_of_work=UnitOfWork(session),
            )

            try:
                applications = application_service.list_applications()
            except ApplicationStorageError as exc:
                abort_on_storage_error(context, exc)

            return applications_pb2.ListApplicationsResponse(
                applications=[
                    applications_pb2.ApplicationResponse(
                        id=str(application.id),
                        name=application.name,
                        repository_url=application.repository_url,
                        status=to_proto_status(application.status),
                    )
                    for application in applications
                ]
            )

    def CreateApplication(
            self,
            request: applications_pb2.CreateApplicationRequest,
            context: grpc.ServicerContext,
    ) -> applications_pb2.ApplicationResponse:
        with self._session_factory() as session:
            repository = PostgresApplicationRepository(session)

            application_service = ApplicationService(
                repository=repository,
                unit_of_work=UnitOfWork(session),
            )

            try:
                application = application_service.create_application(
                    name=request.name,
                    repository_url=request.repository_url,
                )
            except ValueError as exc:
                context.abort(
                    grpc.StatusCode.INVALID_ARGUMENT,
                    str(exc),
                )
            except ApplicationStorageError as exc:
                abort_on_storage_error(context, exc)

            return applications_pb2.ApplicationResponse(
                id=str(application.id),
                name=application.name,
                repository_url=application.repository_url,
                status=to_proto_status(application.status),
            )
