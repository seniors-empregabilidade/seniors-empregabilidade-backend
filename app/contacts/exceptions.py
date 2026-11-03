from app.core.errors import ProblemException


class ProfessionalNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="professional_not_found",
            detail="The professional is not listed for this job.",
        )


class ProfessionalUnavailableError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="professional_unavailable",
            detail="This professional cannot be contacted.",
        )


class CompanyUnavailableError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=403,
            title="Forbidden",
            code="account_unavailable",
            detail="This account cannot access the application.",
        )
