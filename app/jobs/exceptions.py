from app.core.errors import ProblemException


class ClosingDateInThePastError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="closing_date_in_the_past",
            detail="The closing date cannot be in the past.",
            errors={"closing_date": ["The closing date cannot be in the past."]},
        )


class JobNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="job_not_found",
            detail="The job was not found.",
        )


class JobAlreadyOpenError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="job_already_open",
            detail="This job is already open.",
        )


class JobAlreadyClosedError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="job_already_closed",
            detail="This job is already closed.",
        )
