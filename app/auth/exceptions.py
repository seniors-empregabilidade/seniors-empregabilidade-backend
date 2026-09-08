from app.core.errors import ProblemException


class AuthenticationError(ProblemException):
    """Base class for the failure contract of the authentication operation."""


class InvalidCredentialsError(AuthenticationError):
    """The provider rejected the credentials, or the account cannot sign in yet.

    Every provider rejection collapses into this single failure so the response
    never reveals whether the email exists.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            title="Unauthorized",
            code="invalid_credentials",
            detail="The email or password is incorrect.",
        )


class AccountNotActiveError(AuthenticationError):
    """The credentials are valid but the local account may not sign in.

    Raised for suspended and blocked accounts and for an authenticated identity
    with no local record, without distinguishing between them.
    """

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            code="account_not_active",
            detail="This account cannot sign in. Contact support.",
        )


class AuthenticationChallengeRequiredError(AuthenticationError):
    """The provider requires an additional step that this endpoint cannot answer."""

    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            code="authentication_challenge_required",
            detail=(
                "This account requires an additional sign-in step "
                "that is not supported yet."
            ),
        )


class TooManyAttemptsError(AuthenticationError):
    """The provider throttled the request."""

    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            title="Too Many Requests",
            code="too_many_attempts",
            detail="Too many sign-in attempts. Try again later.",
        )


class IdentityProviderUnavailableError(AuthenticationError):
    """The provider is unreachable, misconfigured, or returned an unusable result."""

    def __init__(self) -> None:
        super().__init__(
            status_code=502,
            title="Bad Gateway",
            code="identity_provider_unavailable",
            detail="The identity provider is unavailable.",
        )
