from app.core.errors import ProblemException


class ApplicationNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="application_not_found",
            detail="The application was not found.",
        )


class ApplicationAlreadyClosedError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="application_already_closed",
            detail="This application has already left the selection process.",
        )
