from app.core.errors import ProblemException


class UnsupportedPhotoTypeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="unsupported_photo_type",
            detail="The photo must be a PNG or JPEG file.",
            errors={"file": ["The photo must be a PNG or JPEG file."]},
        )


class PhotoTooLargeError(ProblemException):
    def __init__(self) -> None:
        super().__init__(
            status_code=422,
            title="Validation Error",
            code="photo_too_large",
            detail="The photo must be at most 5 MB.",
            errors={"file": ["The photo must be at most 5 MB."]},
        )
