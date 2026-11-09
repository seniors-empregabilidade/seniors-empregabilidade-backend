from app.core.errors import ProblemException


class TrainingNotFoundError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            title="Not Found",
            code="training_not_found",
            detail="The training was not found.",
        )


class TrainingRelationNotFoundError(ProblemException):
    def __init__(self, field: str) -> None:
        message = "Some of the referenced records do not exist."
        super().__init__(
            status_code=422,
            title="Unprocessable Content",
            code="training_relation_not_found",
            detail=message,
            errors={field: [message]},
        )
