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

LIST_PATH = "/api/v1/admin/accounts"
DETAIL_PATH = f"/api/v1/admin/accounts/{uuid4()}"
STATUS_PATH = f"{DETAIL_PATH}/status"
VALID_BODY = {"status": "blocked", "reason": "Synthetic justification."}


def _as(application: FastAPI, user_type: UserType) -> None:
    application.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=uuid4(), user_type=user_type
    )
    # Any attempt to reach the database would fail on this placeholder, so a
    # 4xx proves the request was rejected before the service ran.
    application.dependency_overrides[get_session] = lambda: object()


@pytest.fixture
def administrator_client(
    application: FastAPI, client: TestClient
) -> Iterator[TestClient]:
    _as(application, UserType.ADMINISTRATOR)
    yield client
    application.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", LIST_PATH), ("GET", DETAIL_PATH), ("PATCH", STATUS_PATH)],
)
def test_requests_without_a_token_are_rejected(
    application: FastAPI, client: TestClient, method: str, path: str
) -> None:
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider

    response = client.request(method, path, json=VALID_BODY)

    assert response.status_code == 401
    assert response.headers["content-type"] == "application/problem+json"


@pytest.mark.parametrize("user_type", [UserType.CANDIDATE, UserType.COMPANY])
@pytest.mark.parametrize(
    ("method", "path"),
    [("GET", LIST_PATH), ("GET", DETAIL_PATH), ("PATCH", STATUS_PATH)],
)
def test_only_administrators_can_manage_accounts(
    application: FastAPI,
    client: TestClient,
    user_type: UserType,
    method: str,
    path: str,
) -> None:
    _as(application, user_type)

    response = client.request(method, path, json=VALID_BODY)

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"
    application.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"user_type": "administrator"}, "query.user_type"),
        ({"account_status": "deleted"}, "query.account_status"),
        ({"company_status": "unknown"}, "query.company_status"),
        ({"min_completion": -1}, "query.min_completion"),
        ({"max_completion": 101}, "query.max_completion"),
        ({"limit": 0}, "query.limit"),
        ({"limit": 101}, "query.limit"),
        ({"offset": -1}, "query.offset"),
    ],
)
def test_invalid_filters_are_rejected_before_listing(
    administrator_client: TestClient, params: dict[str, str | int], field: str
) -> None:
    response = administrator_client.get(LIST_PATH, params=params)

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "validation_error"
    assert list(response.json()["errors"]) == [field]


def test_a_reversed_completion_range_is_rejected(
    administrator_client: TestClient,
) -> None:
    response = administrator_client.get(
        LIST_PATH, params={"min_completion": 80, "max_completion": 20}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_completion_range"
    assert list(response.json()["errors"]) == ["query.min_completion"]


@pytest.mark.parametrize(
    ("body", "field"),
    [
        ({"status": "blocked"}, "body.reason"),
        ({"status": "blocked", "reason": ""}, "body.reason"),
        ({"status": "blocked", "reason": "   "}, "body.reason"),
        ({"status": "blocked", "reason": "x" * 501}, "body.reason"),
        ({"reason": "Synthetic justification."}, "body.status"),
        ({"status": "suspended", "reason": "Synthetic."}, "body.status"),
        ({**VALID_BODY, "user_type": "company"}, "body.user_type"),
    ],
    ids=[
        "missing-reason",
        "empty-reason",
        "blank-reason",
        "long-reason",
        "missing-status",
        "unsupported-status",
        "extra-field",
    ],
)
def test_invalid_status_changes_are_rejected_before_any_change(
    administrator_client: TestClient, body: dict[str, str], field: str
) -> None:
    response = administrator_client.patch(STATUS_PATH, json=body)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert list(response.json()["errors"]) == [field]


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/admin/accounts/not-a-uuid"),
        ("PATCH", "/api/v1/admin/accounts/not-a-uuid/status"),
    ],
)
def test_a_malformed_account_id_is_a_validation_error(
    administrator_client: TestClient, method: str, path: str
) -> None:
    response = administrator_client.request(method, path, json=VALID_BODY)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
