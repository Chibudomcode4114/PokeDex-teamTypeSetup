"""Adapter-specific exceptions for PokeAPI communication.

These exceptions maintain the boundary between external HTTP/PokeAPI concerns
and internal application domains, without exposing httpx or FastAPI HTTPException.
"""


class PokeApiError(Exception):
    """Base exception for all PokeAPI adapter errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PokeApiNotFoundError(PokeApiError):
    """Raised when a requested PokeAPI resource does not exist (HTTP 404).

    This error represents a permanent client failure and is never retried.
    """

    def __init__(self, resource: str) -> None:
        super().__init__(f"PokeAPI resource not found: {resource}", status_code=404)
        self.resource = resource


class PokeApiTransportError(PokeApiError):
    """Raised when network transport fails (e.g. connection error, timeout) after retries."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=None)


class PokeApiServerError(PokeApiError):
    """Raised when PokeAPI returns a 5xx server error after retries are exhausted."""

    def __init__(self, status_code: int, message: str | None = None) -> None:
        msg = message or f"PokeAPI server error with HTTP status {status_code}"
        super().__init__(msg, status_code=status_code)


class PokeApiRateLimitError(PokeApiError):
    """Raised when PokeAPI returns HTTP 429 Too Many Requests after retries are exhausted."""

    def __init__(self, message: str | None = None) -> None:
        msg = message or "PokeAPI rate limit exceeded (HTTP 429)"
        super().__init__(msg, status_code=429)


class PokeApiNormalizationError(PokeApiError):
    """Raised when raw PokeAPI payload is missing required fields or cannot be normalized."""

    def __init__(self, message: str) -> None:
        super().__init__(f"PokeAPI normalization error: {message}")

