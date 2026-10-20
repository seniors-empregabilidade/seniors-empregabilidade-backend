from dataclasses import dataclass
from typing import Final

MAX_DOCUMENT_BYTES: Final = 5 * 1024 * 1024
MAX_FILENAME_LENGTH: Final = 255
_SIGNATURES: Final = (
    (b"%PDF-", "application/pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
)
_DEFAULT_NAMES: Final = {
    "application/pdf": "certificate.pdf",
    "image/png": "certificate.png",
    "image/jpeg": "certificate.jpg",
}


class UnsupportedDocumentValueError(ValueError):
    """The content is not a PDF, PNG, or JPEG file."""


class DocumentTooLargeValueError(ValueError):
    """The content exceeds the maximum document size."""


@dataclass(frozen=True, slots=True)
class CertificateDocument:
    filename: str
    content_type: str
    content: bytes

    @classmethod
    def parse(cls, filename: str | None, content: bytes) -> CertificateDocument:
        if len(content) > MAX_DOCUMENT_BYTES:
            raise DocumentTooLargeValueError
        # The declared type and extension are client-controlled; only the bytes count.
        content_type = next(
            (kind for magic, kind in _SIGNATURES if content.startswith(magic)), None
        )
        if content_type is None:
            raise UnsupportedDocumentValueError
        name = _base_name(filename or "") or _DEFAULT_NAMES[content_type]
        return cls(name, content_type, content)


def _base_name(filename: str) -> str:
    base = filename.replace("\\", "/").rsplit("/", 1)[-1]
    printable = "".join(char for char in base if char.isprintable())
    return printable.strip()[-MAX_FILENAME_LENGTH:]
