"""Domain error hierarchy.

Errors carry a stable machine-readable `code`, an HTTP status for the API layer and a
`retryable` flag the task runner uses to decide between retrying and failing permanently.
Messages must be safe to show to the user: never include secrets or raw upstream payloads.
"""

from __future__ import annotations

from typing import Any, ClassVar


class CareerOSError(Exception):
    code: ClassVar[str] = "careeros_error"
    http_status: ClassVar[int] = 500
    retryable: bool = False  # class default; instances may override (e.g. throttling vs denied)

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
        retryable: bool | None = None,
    ):
        self.message = message or self.__class__.__doc__ or self.code
        self.details = details or {}
        if retryable is not None:
            self.retryable = retryable
        super().__init__(self.message)


# --- Generic API errors ----------------------------------------------------------------


class NotFoundError(CareerOSError):
    """The requested resource does not exist."""

    code = "not_found"
    http_status = 404


class PermissionDeniedError(CareerOSError):
    """You do not have access to this resource."""

    code = "permission_denied"
    http_status = 403


class AuthenticationError(CareerOSError):
    """Authentication is required."""

    code = "unauthenticated"
    http_status = 401


class ValidationFailedError(CareerOSError):
    """The request could not be validated."""

    code = "validation_failed"
    http_status = 422


class ConflictError(CareerOSError):
    """The resource is in a state that does not allow this operation."""

    code = "conflict"
    http_status = 409


class RateLimitedError(CareerOSError):
    """Too many requests; slow down."""

    code = "rate_limited"
    http_status = 429


class ConfigurationError(CareerOSError):
    """A required integration is not configured."""

    code = "configuration_error"
    http_status = 503


# --- Pipeline errors (spec §66) --------------------------------------------------------


class SourceFetchError(CareerOSError):
    """A job source could not be fetched."""

    code = "source_fetch_error"
    http_status = 502
    retryable = True


class JobExtractionError(CareerOSError):
    """The job description could not be analysed."""

    code = "job_extraction_error"
    http_status = 502
    retryable = True


class LLMProviderError(CareerOSError):
    """The AI provider failed to produce a valid response."""

    code = "llm_provider_error"
    http_status = 502
    retryable = True


class ResumeCompilationError(CareerOSError):
    """The resume could not be compiled to PDF."""

    code = "resume_compilation_error"
    http_status = 500


class ContactVerificationError(CareerOSError):
    """The contact information could not be verified."""

    code = "contact_verification_error"
    http_status = 422


class EmailProviderError(CareerOSError):
    """The email provider rejected or failed the request."""

    code = "email_provider_error"
    http_status = 502
    retryable = True


class PortalDetectionError(CareerOSError):
    """The application portal could not be identified."""

    code = "portal_detection_error"
    http_status = 422


class PortalUnsupportedError(CareerOSError):
    """This application portal is not supported yet."""

    code = "portal_unsupported"
    http_status = 422


class FormStructureChangedError(CareerOSError):
    """The application form no longer matches what was reviewed."""

    code = "form_structure_changed"
    http_status = 409


class AuthenticationRequiredError(CareerOSError):
    """The portal requires you to sign in before continuing."""

    code = "portal_authentication_required"
    http_status = 409


class CaptchaDetectedError(CareerOSError):
    """The portal presented a CAPTCHA; manual action is required."""

    code = "captcha_detected"
    http_status = 409


class ApplicationSubmissionError(CareerOSError):
    """The application could not be submitted."""

    code = "application_submission_error"
    http_status = 502
