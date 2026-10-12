from app.core.errors import ProblemException


class NotificationNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="notification_not_found",
            detail="The notification was not found.",
        )
