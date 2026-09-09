from app.core.errors import ProblemException


class EmailVerificationError(ProblemException):
    """Base class for the failure contract of the email verification operation."""


class InvalidVerificationCodeError(EmailVerificationError):
    """The code does not match, or there is nothing to verify for that address.

    A wrong code and an unknown address collapse into this single failure so the
    response never reveals which emails exist in this database.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Unprocessable Content",
            code="invalid_verification_code",
            detail="The verification code is invalid.",
        )


class VerificationCodeExpiredError(EmailVerificationError):
    """The code was issued for this address but is past its validity window.

    Kept distinct from an invalid code because the next action differs: request a
    new code rather than retype the one already received.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Unprocessable Content",
            code="verification_code_expired",
            detail="The verification code has expired. Request a new one.",
        )


class ResendTooSoonError(EmailVerificationError):
    """A resend was requested inside the cooldown window."""

    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            title="Too Many Requests",
            code="verification_resend_too_soon",
            detail=(
                "A verification code was sent recently. "
                "Wait a moment before requesting another."
            ),
        )


class ResendLimitReachedError(EmailVerificationError):
    """The account exhausted its resend allowance for the current window."""

    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            title="Too Many Requests",
            code="verification_resend_limit_reached",
            detail="Too many verification codes were requested. Try again later.",
        )


class TooManyVerificationAttemptsError(EmailVerificationError):
    """The provider throttled the account after repeated wrong codes.

    Distinct from the resend limits: this one is spent by failed confirmations,
    so telling the user to wait for a new code would be wrong advice.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            title="Too Many Requests",
            code="too_many_verification_attempts",
            detail="Too many verification attempts. Try again later.",
        )


class EmailVerificationProviderUnavailableError(EmailVerificationError):
    """The provider is unreachable, misconfigured, or returned an unusable result."""

    def __init__(self) -> None:
        super().__init__(
            status_code=502,
            title="Bad Gateway",
            code="email_verification_provider_unavailable",
            detail="The verification service is unavailable.",
        )
