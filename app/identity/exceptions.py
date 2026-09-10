from app.core.errors import ProblemException


class IdentityProviderUnavailableError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            title="Service Unavailable",
            code="identity_provider_unavailable",
            detail="The identity provider is temporarily unavailable.",
        )


class InvalidCredentialsError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            title="Unauthorized",
            code="invalid_credentials",
            detail="The email or password is incorrect.",
        )


class InvalidAccessTokenError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=401,
            title="Unauthorized",
            code="invalid_access_token",
            detail="A valid access token is required.",
        )


class IdentityConflictError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="identity_conflict",
            detail="The identity could not be linked to this registration.",
        )


class IdentityConfirmationRequiredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="identity_confirmation_required",
            detail="Confirm the email before continuing.",
        )


class IdentityPasswordRejectedError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="password_policy_violation",
            detail="The password does not meet the identity provider policy.",
            errors={"password": ["The password does not meet the required policy."]},
        )


class IdentityRateLimitError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=429,
            title="Too Many Requests",
            code="too_many_attempts",
            detail="Too many attempts. Try again later.",
        )


class InvalidConfirmationCodeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_verification_code",
            detail="The verification code is invalid or expired.",
            errors={"code": ["The verification code is invalid or expired."]},
        )


class AuthenticationChallengeRequiredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            code="authentication_challenge_required",
            detail="This account requires an additional sign-in step.",
        )
