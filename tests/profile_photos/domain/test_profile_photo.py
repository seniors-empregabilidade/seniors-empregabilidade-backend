import pytest

from app.profile_photos.domain.profile_photo import (
    MAX_PHOTO_BYTES,
    PhotoTooLargeValueError,
    ProfilePhoto,
    UnsupportedPhotoValueError,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 8
PDF = b"%PDF-1.7\n"


def test_parse_accepts_png_bytes() -> None:
    """Test that PNG bytes are correctly identified and assigned the correct content_type."""
    result = ProfilePhoto.parse("photo.png", PNG)
    assert result.content_type == "image/png"
    assert result.content == PNG


def test_parse_accepts_jpeg_bytes() -> None:
    """Test that JPEG bytes are correctly identified and assigned the correct content_type."""
    result = ProfilePhoto.parse("photo.jpg", JPEG)
    assert result.content_type == "image/jpeg"
    assert result.content == JPEG


def test_parse_rejects_pdf_disguised_as_png() -> None:
    """Test that PDF is rejected even when filename claims .png (magic bytes win)."""
    with pytest.raises(UnsupportedPhotoValueError):
        ProfilePhoto.parse("x.png", PDF)


def test_parse_rejects_plain_text() -> None:
    """Test that plain text is rejected as unsupported."""
    with pytest.raises(UnsupportedPhotoValueError):
        ProfilePhoto.parse("text.txt", b"hello")


def test_parse_rejects_oversized() -> None:
    """Test that files over MAX_PHOTO_BYTES are rejected."""
    oversized_png = PNG + b"\x00" * MAX_PHOTO_BYTES
    with pytest.raises(PhotoTooLargeValueError):
        ProfilePhoto.parse("big.png", oversized_png)


def test_parse_accepts_max_size_png() -> None:
    """Test that files exactly at MAX_PHOTO_BYTES are accepted."""
    max_size_png = PNG + b"\x00" * (MAX_PHOTO_BYTES - len(PNG))
    result = ProfilePhoto.parse("max.png", max_size_png)
    assert len(result.content) == MAX_PHOTO_BYTES


def test_parse_defaults_filename_for_png() -> None:
    """Test that filename defaults to photo.png when None."""
    result = ProfilePhoto.parse(None, PNG)
    assert result.filename == "photo.png"


def test_parse_defaults_filename_for_jpeg() -> None:
    """Test that filename defaults to photo.jpg when filename is empty string."""
    result = ProfilePhoto.parse("", JPEG)
    assert result.filename == "photo.jpg"


@pytest.mark.parametrize(
    "content,content_type",
    [(PNG, "image/png"), (JPEG, "image/jpeg")],
)
def test_supported_types_are_detected_from_the_bytes(
    content: bytes, content_type: str
) -> None:
    """Test that supported photo types are detected from magic bytes."""
    assert ProfilePhoto.parse("file", content).content_type == content_type


def test_the_extension_does_not_decide_the_type() -> None:
    """Test that filename extension does not override magic byte detection."""
    assert ProfilePhoto.parse("photo.png", JPEG).content_type == "image/jpeg"


@pytest.mark.parametrize(
    "content", [b"", b"<html><script>", b"MZ\x90\x00", b"GIF89a", b"%PD", b"\xff\xd8"]
)
def test_other_content_is_rejected(content: bytes) -> None:
    """Test that unsupported content types are rejected."""
    with pytest.raises(UnsupportedPhotoValueError):
        ProfilePhoto.parse("photo.jpg", content)
