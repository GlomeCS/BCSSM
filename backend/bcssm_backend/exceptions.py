"""Custom exception hierarchy for BCSSM application."""


class BaseError(Exception):
    """Base exception for all BCSSM application errors."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class DatabaseError(BaseError):
    """Raised when a database operation fails."""

    def __init__(self, message: str = "A database error occurred", status_code: int = 500):
        super().__init__(message, status_code)


class CacheError(BaseError):
    """Raised when a cache operation fails."""

    def __init__(self, message: str = "A cache error occurred", status_code: int = 500):
        super().__init__(message, status_code)


class ValidationError(BaseError):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation error", status_code: int = 400):
        super().__init__(message, status_code)


class AuthenticationError(BaseError):
    """Raised when authentication fails or a user is not authenticated."""

    def __init__(self, message: str = "Authentication required", status_code: int = 401):
        super().__init__(message, status_code)


class NotFoundError(BaseError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str = "Resource not found", status_code: int = 404):
        super().__init__(message, status_code)
