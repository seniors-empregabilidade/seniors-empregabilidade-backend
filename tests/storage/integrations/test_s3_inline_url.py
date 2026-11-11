from urllib.parse import parse_qs, urlparse

import pytest

from app.storage.exceptions import DocumentStorageUnavailableError
from app.storage.integrations.s3 import S3DocumentStorage

BUCKET = "synthetic-uploads"


@pytest.fixture
def storage() -> S3DocumentStorage:
    return S3DocumentStorage(
        bucket=BUCKET,
        region="us-east-2",
        access_key_id="synthetic",
        secret_access_key="synthetic",
    )


def test_missing_bucket_raises_unavailable_on_inline_url() -> None:
    storage = S3DocumentStorage(bucket="", region="us-east-2")

    with pytest.raises(DocumentStorageUnavailableError):
        storage.inline_url("key", content_type="application/pdf", expires_in=60)


def test_inline_url_returns_presigned_get_without_attachment_disposition(
    storage: S3DocumentStorage,
) -> None:
    url = storage.inline_url(
        "certifications/a/b",
        content_type="application/pdf",
        expires_in=300,
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.hostname == f"{BUCKET}.s3.us-east-2.amazonaws.com"
    assert parsed.path == "/certifications/a/b"
    assert query["X-Amz-Expires"] == ["300"]
    assert query["response-content-type"] == ["application/pdf"]
    # Inline should NOT include response-content-disposition
    assert "response-content-disposition" not in query
