from collections.abc import Iterator

import pytest
from fastapi import FastAPI, UploadFile
from fastapi.testclient import TestClient

from app.candidates.domain.certificate_document import MAX_DOCUMENT_BYTES
from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.errors import register_exception_handlers

LIMIT = 1024


@pytest.fixture
def received() -> list[int]:
    return []


@pytest.fixture
def limited_client(received: list[int]) -> Iterator[TestClient]:
    app = FastAPI()
    register_exception_handlers(app)
    app.add_middleware(RequestBodyLimitMiddleware, max_bytes=LIMIT)

    @app.put("/upload")
    def upload(file: UploadFile) -> dict[str, int]:
        received.append(len(file.file.read()))
        return {"size": received[-1]}

    with TestClient(app, raise_server_exceptions=False) as client:
        yield client


def chunks(total: int) -> Iterator[bytes]:
    for _ in range(total // 256):
        yield b"x" * 256


def test_a_body_within_the_limit_reaches_the_route(
    limited_client: TestClient, received: list[int]
) -> None:
    response = limited_client.put("/upload", files={"file": ("a.pdf", b"x" * 100)})

    assert response.status_code == 200
    assert received == [100]


def test_a_declared_oversized_body_is_refused_before_parsing(
    limited_client: TestClient, received: list[int]
) -> None:
    response = limited_client.put(
        "/upload", files={"file": ("a.pdf", b"x" * (LIMIT + 1))}
    )

    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "http_413"
    assert received == []


def test_an_oversized_body_without_content_length_is_refused(
    limited_client: TestClient, received: list[int]
) -> None:
    response = limited_client.put(
        "/upload",
        content=chunks(LIMIT * 4),
        headers={"content-type": "multipart/form-data; boundary=synthetic"},
    )

    assert response.status_code == 413
    assert received == []


def test_an_anonymous_oversized_upload_is_refused_before_authentication(
    client: TestClient,
) -> None:
    response = client.put(
        "/api/v1/professionals/me/certifications/"
        "00000000-0000-4000-8000-000000000001/document",
        files={"file": ("a.pdf", b"%PDF-" + b"x" * (MAX_DOCUMENT_BYTES + 65 * 1024))},
    )

    assert response.status_code == 413
