from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlsplit
from uuid import UUID


class ApplicationStatus(str, Enum):
    REGISTERED = "registered"
    DEPLOYED = "deployed"
    FAILED = "failed"


@dataclass(frozen=True)
class Application:
    id: UUID
    name: str
    repository_url: str
    status: ApplicationStatus

    def __post_init__(self):
        if not isinstance(self.id, UUID):
            raise ValueError("Application id must be a UUID")

        if not isinstance(self.name, str):
            raise ValueError("Application name must be a string")

        if not 3 <= len(self.name) <= 100:
            raise ValueError(
                "Application name must contain between 3 and 100 characters"
            )

        if not isinstance(self.repository_url, str):
            raise ValueError("Repository URL must be a string")

        try:
            parsed_url = urlsplit(self.repository_url)
            hostname = parsed_url.hostname
            port = parsed_url.port
        except ValueError as exc:
            raise ValueError("Repository URL is invalid") from exc

        if (
                parsed_url.scheme not in ("http", "https")
                or not hostname
                or any(character.isspace() for character in self.repository_url)
        ):
            raise ValueError(
                "Repository URL must be a valid HTTP or HTTPS URL"
            )

        if not isinstance(self.status, ApplicationStatus):
            raise ValueError("Invalid application status")
