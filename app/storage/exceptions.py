from app.core.errors import ProblemException


class DocumentStorageUnavailableError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            title="Service Unavailable",
            code="document_storage_unavailable",
            detail="The document storage is temporarily unavailable.",
        )
