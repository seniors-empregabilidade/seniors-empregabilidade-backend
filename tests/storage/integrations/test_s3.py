from collections.abc import Iterator
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from botocore.stub import Stubber

from app.storage.exceptions import DocumentStorageUnavailableError
from app.storage.integrations.s3 import S3DocumentStorage, attachment

BUCKET = "synthetic-uploads"


@pytest.fixture
def storage() -> S3DocumentStorage:
    return S3DocumentStorage(
        bucket=BUCKET,
        region="us-east-2",
        access_key_id="synthetic",
        secret_access_key="synthetic",
    )


@pytest.fixture
def stub(storage: S3DocumentStorage) -> Iterator[Stubber]:
    with Stubber(storage._client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_missing_bucket_is_unavailable_on_use() -> None:
    storage = S3DocumentStorage(bucket="", region="us-east-2")

    with pytest.raises(DocumentStorageUnavailableError):
        storage.put("key", b"%PDF-", content_type="application/pdf")
    with pytest.raises(DocumentStorageUnavailableError):
        storage.delete("key")
    with pytest.raises(DocumentStorageUnavailableError):
        storage.download_url(
            "key", filename="a.pdf", content_type="application/pdf", expires_in=60
        )


def test_put_sends_the_content_type(storage: S3DocumentStorage, stub: Stubber) -> None:
    stub.add_response(
        "put_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": "certifications/a/b",
            "Body": b"%PDF-1.7",
            "ContentType": "application/pdf",
        },
    )

    storage.put("certifications/a/b", b"%PDF-1.7", content_type="application/pdf")


def test_delete_targets_the_key(storage: S3DocumentStorage, stub: Stubber) -> None:
    stub.add_response("delete_object", {}, {"Bucket": BUCKET, "Key": "key"})

    storage.delete("key")


def test_put_error_is_unavailable(storage: S3DocumentStorage, stub: Stubber) -> None:
    stub.add_client_error("put_object", "AccessDenied", http_status_code=403)

    with pytest.raises(DocumentStorageUnavailableError):
        storage.put("key", b"%PDF-", content_type="application/pdf")


def test_delete_error_is_unavailable(storage: S3DocumentStorage, stub: Stubber) -> None:
    stub.add_client_error("delete_object", "AccessDenied", http_status_code=403)

    with pytest.raises(DocumentStorageUnavailableError):
        storage.delete("key")


def test_download_url_forces_an_attachment_and_expires(
    storage: S3DocumentStorage,
) -> None:
    url = storage.download_url(
        "certifications/a/b",
        filename="certificado.pdf",
        content_type="application/pdf",
        expires_in=300,
    )

    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    assert parsed.hostname == f"{BUCKET}.s3.us-east-2.amazonaws.com"
    assert parsed.path == "/certifications/a/b"
    assert query["X-Amz-Expires"] == ["300"]
    assert query["response-content-type"] == ["application/pdf"]
    assert query["response-content-disposition"][0].startswith("attachment;")


def test_local_endpoint_uses_path_addressing() -> None:
    storage = S3DocumentStorage(
        bucket=BUCKET,
        region="us-east-2",
        endpoint_url="http://localhost:9000",
        access_key_id="synthetic",
        secret_access_key="synthetic",
    )

    url = storage.download_url(
        "key", filename="a.pdf", content_type="application/pdf", expires_in=60
    )

    assert url.startswith(f"http://localhost:9000/{BUCKET}/key?")


def test_attachment_keeps_unicode_names_and_an_ascii_fallback() -> None:
    header = attachment('certificação "final".pdf')

    fallback, encoded = header.split("; filename*=UTF-8''")
    assert fallback == 'attachment; filename="certificao final.pdf"'
    assert unquote(encoded) == 'certificação "final".pdf'
