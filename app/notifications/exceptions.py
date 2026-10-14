from app.core.errors import ProblemException


class NotificationNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="notification_not_found",
            detail="The notification was not found.",
        )


class InvalidNotificationCursorError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="invalid_cursor",
            detail="The pagination cursor is invalid.",
            errors={"query.cursor": ["The cursor is invalid."]},
        )
