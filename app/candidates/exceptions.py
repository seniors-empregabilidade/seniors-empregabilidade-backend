from app.core.errors import ProblemException


class InvalidCpfError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_cpf",
            detail="The CPF is invalid.",
            errors={"cpf": ["The CPF is invalid."]},
        )


class MinimumAgeNotMetError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="minimum_age_not_met",
            detail="The professional must be at least 45 years old.",
            errors={"birth_date": ["The minimum age is 45."]},
        )


class TermsAcceptanceRequiredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="terms_acceptance_required",
            detail="The current terms must be accepted.",
            errors={"terms_version_accepted": ["The terms version is required."]},
        )


class CpfAlreadyRegisteredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="cpf_already_registered",
            detail="The CPF is already registered.",
            errors={"cpf": ["The CPF is already registered."]},
        )


class EmailAlreadyRegisteredError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="email_already_registered",
            detail="The email is already registered.",
            errors={"email": ["The email is already registered."]},
        )


class ProfileNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="profile_not_found",
            detail="The professional profile was not found.",
        )
