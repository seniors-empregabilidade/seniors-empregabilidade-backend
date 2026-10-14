from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.auth.schemas.current_user import CurrentUser
from app.db.models.enums import UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider


@pytest.fixture
def authenticated_client(
    application: FastAPI, client: TestClient
) -> Iterator[TestClient]:
    application.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uuid4(), user_type=UserType.CANDIDATE
    )
    yield client
    application.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/notifications/me"),
        ("POST", "/api/v1/notifications/me/read-all"),
        ("POST", f"/api/v1/notifications/{uuid4()}/read"),
    ],
)
def test_requests_without_a_token_are_rejected(
    application: FastAPI, client: TestClient, method: str, path: str
) -> None:
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider

    response = client.request(method, path)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


@pytest.fixture
def offline_client(
    application: FastAPI, authenticated_client: TestClient
) -> TestClient:
    # The listing would fail on this placeholder, so a 422 proves it never ran.
    application.dependency_overrides[get_session] = lambda: object()
    return authenticated_client


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "query.limit"),
        ({"limit": 101}, "query.limit"),
        ({"cursor": ""}, "query.cursor"),
        ({"cursor": "a" * 201}, "query.cursor"),
    ],
    ids=["limit-zero", "limit-above-max", "empty-cursor", "long-cursor"],
)
def test_invalid_pagination_is_rejected_before_listing(
    offline_client: TestClient, params: dict[str, str | int], field: str
) -> None:
    response = offline_client.get("/api/v1/notifications/me", params=params)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "validation_error"
    assert list(response.json()["errors"]) == [field]


def test_foreign_cursor_is_rejected_before_listing(
    offline_client: TestClient,
) -> None:
    response = offline_client.get(
        "/api/v1/notifications/me", params={"cursor": "not-a-cursor"}
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_cursor"
    assert list(response.json()["errors"]) == ["query.cursor"]


def test_malformed_notification_id_is_a_validation_error(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post("/api/v1/notifications/not-a-uuid/read")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
