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


class ApplicationAlreadyExistsError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="application_already_exists",
            detail="You have already applied to this job.",
        )


class JobNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="job_not_found",
            detail="The job was not found.",
        )


class JobNotOpenError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="job_not_open",
            detail="This job is not open for applications.",
        )
