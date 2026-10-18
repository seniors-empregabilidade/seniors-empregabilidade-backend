from app.core.errors import ProblemException


class AccountNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="account_not_found",
            detail="The account was not found.",
        )


class AccountAlreadyBlockedError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="account_already_blocked",
            detail="The account is already blocked.",
        )


class AccountAlreadyActiveError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=409,
            title="Conflict",
            code="account_already_active",
            detail="The account is already active.",
        )


class InvalidCompletionRangeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_completion_range",
            detail="The minimum completion cannot exceed the maximum completion.",
            errors={
                "query.min_completion": [
                    "The minimum completion cannot exceed the maximum completion."
                ]
            },
        )
