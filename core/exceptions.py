class AppError(Exception):
    """Base class for domain errors that map to a specific HTTP status."""

    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: str | None = None) -> None:
        if detail is not None:
            self.detail = detail
        super().__init__(self.detail)


class DuplicateEmailError(AppError):
    status_code = 409
    detail = "A student with this email already exists"


class PersonnelNotFoundError(AppError):
    status_code = 404
    detail = "Personnel not found"


class MediaOutletNotFoundError(AppError):
    status_code = 404
    detail = "Media outlet not found"


class DuplicatePersonnelEmailError(AppError):
    status_code = 409
    detail = "A personnel record with this email already exists"


class LLMNotConfiguredError(AppError):
    # Callers normally pass the exact missing env var as the detail (e.g.
    # "ANTHROPIC_API_KEY is not set on the server"); this is the generic fallback.
    status_code = 503
    detail = "No API key is configured for the requested model"


class LLMServiceError(AppError):
    status_code = 502
    detail = "The language model could not be reached"