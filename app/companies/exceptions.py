from app.core.errors import ProblemException


class CompanyProfileNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="company_profile_not_found",
            detail="The company profile was not found.",
        )
