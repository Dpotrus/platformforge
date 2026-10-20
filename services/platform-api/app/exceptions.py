class ApplicationError(Exception):
    """Base exception for application-level errors."""


class ApplicationStorageError(ApplicationError):
    """Raised when an application storage operation fails."""


class ApplicationStorageUnavailable(ApplicationStorageError):
    """Raised when application storage is temporarily unavailable."""
