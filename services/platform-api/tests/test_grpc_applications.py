import grpc
import pytest

from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

from app.domain.application import Application, ApplicationStatus
from app.grpc.applications import ApplicationServiceServicer
from platformforge.v1 import applications_pb2

from app.exceptions import (
    ApplicationStorageError,
    ApplicationStorageUnavailable,
)


def test_list_applications_returns_proto_applications() -> None:
    application_id = uuid4()

    domain_application = Application(
        id=application_id,
        name="example-app",
        repository_url="https://gitlab.com/example/app",
        status=ApplicationStatus.REGISTERED,
    )

    session = Mock()

    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    session_factory = Mock(return_value=session_context)

    application_service = Mock()
    application_service.list_applications.return_value = [
        domain_application,
    ]

    with patch(
            "app.grpc.applications.ApplicationService",
            return_value=application_service,
    ):
        servicer = ApplicationServiceServicer(
            session_factory=session_factory,
        )

        response = servicer.ListApplications(
            applications_pb2.ListApplicationsRequest(),
            Mock(),
        )

    application_service.list_applications.assert_called_once_with()
    session_factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()

    assert len(response.applications) == 1

    proto_application = response.applications[0]

    assert proto_application.id == str(application_id)
    assert proto_application.name == "example-app"
    assert proto_application.repository_url == "https://gitlab.com/example/app"
    assert (
            proto_application.status
            == applications_pb2.APPLICATION_STATUS_REGISTERED
    )

def test_create_application_returns_proto_application() -> None:
    application_id = uuid4()

    domain_application = Application(
        id=application_id,
        name="example-app",
        repository_url="https://gitlab.com/example/app",
        status=ApplicationStatus.REGISTERED,
    )

    session = Mock()

    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    session_factory = Mock(return_value=session_context)

    application_service = Mock()
    application_service.create_application.return_value = domain_application

    with patch(
            "app.grpc.applications.ApplicationService",
            return_value=application_service,
    ):
        servicer = ApplicationServiceServicer(
            session_factory=session_factory,
        )

        response = servicer.CreateApplication(
            applications_pb2.CreateApplicationRequest(
                name="example-app",
                repository_url="https://gitlab.com/example/app",
            ),
            Mock(),
        )

    application_service.create_application.assert_called_once_with(
        name="example-app",
        repository_url="https://gitlab.com/example/app",
    )

    session_factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()

    assert isinstance(response, applications_pb2.ApplicationResponse)
    assert response.id == str(application_id)
    assert response.name == "example-app"
    assert response.repository_url == "https://gitlab.com/example/app"
    assert response.status == applications_pb2.APPLICATION_STATUS_REGISTERED

def test_create_application_invalid_argument() -> None:
    session = Mock()

    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    session_factory = Mock(return_value=session_context)

    application_service = Mock()
    application_service.create_application.side_effect = ValueError(
        "Application name must be at least 3 characters"
    )

    context = Mock()
    context.abort.side_effect = RuntimeError("RPC aborted")

    with patch(
            "app.grpc.applications.ApplicationService",
            return_value=application_service,
    ):
        servicer = ApplicationServiceServicer(
            session_factory=session_factory,
        )

        with pytest.raises(RuntimeError, match="RPC aborted"):
            servicer.CreateApplication(
                applications_pb2.CreateApplicationRequest(
                    name="ab",
                    repository_url="https://gitlab.com/example/app",
                ),
                context,
            )

    context.abort.assert_called_once_with(
        grpc.StatusCode.INVALID_ARGUMENT,
        "Application name must be at least 3 characters",
    )

    session_factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()

@pytest.mark.parametrize(
    ("storage_error", "expected_status", "expected_message"),
    [
        (
                ApplicationStorageUnavailable("Connection refused"),
                grpc.StatusCode.UNAVAILABLE,
                "Service temporarily unavailable",
        ),
        (
                ApplicationStorageError("Database query failed"),
                grpc.StatusCode.INTERNAL,
                "Database operation failed",
        ),
    ],
)
def test_list_applications_handles_storage_errors(
        storage_error: ApplicationStorageError,
        expected_status: grpc.StatusCode,
        expected_message: str,
) -> None:
    session = Mock()

    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    session_factory = Mock(return_value=session_context)

    application_service = Mock()
    application_service.list_applications.side_effect = storage_error

    context = Mock()
    context.abort.side_effect = RuntimeError("RPC aborted")

    with patch(
            "app.grpc.applications.ApplicationService",
            return_value=application_service,
    ):
        servicer = ApplicationServiceServicer(
            session_factory=session_factory,
        )

        with pytest.raises(RuntimeError, match="RPC aborted"):
            servicer.ListApplications(
                applications_pb2.ListApplicationsRequest(),
                context,
            )

    application_service.list_applications.assert_called_once_with()

    context.abort.assert_called_once_with(
        expected_status,
        expected_message,
    )

    session_factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()


@pytest.mark.parametrize(
    ("storage_error", "expected_status", "expected_message"),
    [
        (
                ApplicationStorageUnavailable("Connection refused"),
                grpc.StatusCode.UNAVAILABLE,
                "Service temporarily unavailable",
        ),
        (
                ApplicationStorageError("Database query failed"),
                grpc.StatusCode.INTERNAL,
                "Database operation failed",
        ),
    ],
)
def test_create_application_handles_storage_errors(
        storage_error: ApplicationStorageError,
        expected_status: grpc.StatusCode,
        expected_message: str,
) -> None:
    session = Mock()

    session_context = MagicMock()
    session_context.__enter__.return_value = session
    session_context.__exit__.return_value = False

    session_factory = Mock(return_value=session_context)

    application_service = Mock()
    application_service.create_application.side_effect = storage_error

    context = Mock()
    context.abort.side_effect = RuntimeError("RPC aborted")

    with patch(
            "app.grpc.applications.ApplicationService",
            return_value=application_service,
    ):
        servicer = ApplicationServiceServicer(
            session_factory=session_factory,
        )

        with pytest.raises(RuntimeError, match="RPC aborted"):
            servicer.CreateApplication(
                applications_pb2.CreateApplicationRequest(
                    name="example-app",
                    repository_url="https://gitlab.com/example/app",
                ),
                context,
            )

    application_service.create_application.assert_called_once_with(
        name="example-app",
        repository_url="https://gitlab.com/example/app",
    )

    context.abort.assert_called_once_with(
        expected_status,
        expected_message,
    )

    session_factory.assert_called_once_with()
    session_context.__exit__.assert_called_once()
