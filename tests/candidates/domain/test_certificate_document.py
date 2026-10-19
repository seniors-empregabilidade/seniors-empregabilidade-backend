import pytest

from app.candidates.domain.certificate_document import (
    MAX_DOCUMENT_BYTES,
    CertificateDocument,
    DocumentTooLargeValueError,
    UnsupportedDocumentValueError,
)

PDF = b"%PDF-1.7\n"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8


@pytest.mark.parametrize(
    "content,content_type",
    [(PDF, "application/pdf"), (PNG, "image/png"), (JPEG, "image/jpeg")],
)
def test_supported_types_are_detected_from_the_bytes(
    content: bytes, content_type: str
) -> None:
    assert CertificateDocument.parse("file", content).content_type == content_type


def test_the_extension_does_not_decide_the_type() -> None:
    assert CertificateDocument.parse("photo.png", PDF).content_type == "application/pdf"


@pytest.mark.parametrize(
    "content", [b"", b"<html><script>", b"MZ\x90\x00", b"GIF89a", b"%PD"]
)
def test_other_content_is_rejected(content: bytes) -> None:
    with pytest.raises(UnsupportedDocumentValueError):
        CertificateDocument.parse("certificate.pdf", content)


def test_content_at_the_limit_is_accepted() -> None:
    content = PDF + b"\x00" * (MAX_DOCUMENT_BYTES - len(PDF))

    assert (
        len(CertificateDocument.parse("a.pdf", content).content) == MAX_DOCUMENT_BYTES
    )


def test_content_over_the_limit_is_rejected() -> None:
    with pytest.raises(DocumentTooLargeValueError):
        CertificateDocument.parse("a.pdf", PDF + b"\x00" * MAX_DOCUMENT_BYTES)


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("C:\\Users\\maria\\certificado.pdf", "certificado.pdf"),
        ("../../etc/certificado.pdf", "certificado.pdf"),
        ("  certi\x00ficado\n.pdf ", "certificado.pdf"),
        (None, "certificate.pdf"),
        ("", "certificate.pdf"),
        ("dir/", "certificate.pdf"),
    ],
)
def test_filename_is_reduced_to_a_printable_base_name(
    filename: str | None, expected: str
) -> None:
    assert CertificateDocument.parse(filename, PDF).filename == expected


def test_long_filename_keeps_its_extension() -> None:
    name = CertificateDocument.parse("a" * 300 + ".pdf", PDF).filename

    assert len(name) == 255
    assert name.endswith(".pdf")
