from dataclasses import dataclass
from typing import Final

# Must stay in sync with MAX_DOCUMENT_BYTES in app/candidates/domain/certificate_document.py
# A global request-body-limit middleware depends on them being equal.
MAX_PHOTO_BYTES: Final = 5 * 1024 * 1024
MAX_FILENAME_LENGTH: Final = 255
_SIGNATURES: Final = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)
_DEFAULT_NAMES: Final = {
    "image/png": "photo.png",
    "image/jpeg": "photo.jpg",
}


class UnsupportedPhotoValueError(ValueError):
    """The content is not a PNG or JPEG file."""


class PhotoTooLargeValueError(ValueError):
    """The content exceeds the maximum photo size."""


@dataclass(frozen=True, slots=True)
class ProfilePhoto:
    filename: str
    content_type: str
    content: bytes

    @classmethod
    def parse(cls, filename: str | None, content: bytes) -> ProfilePhoto:
        if len(content) > MAX_PHOTO_BYTES:
            raise PhotoTooLargeValueError
        # The declared type and extension are client-controlled; only the bytes count.
        content_type = next(
            (kind for magic, kind in _SIGNATURES if content.startswith(magic)), None
        )
        if content_type is None:
            raise UnsupportedPhotoValueError
        name = _base_name(filename or "") or _DEFAULT_NAMES[content_type]
        return cls(name, content_type, content)


def _base_name(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    printable = "".join(char for char in base if char.isprintable())
    return printable.strip()[-MAX_FILENAME_LENGTH:]
