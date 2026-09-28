from collections.abc import Iterator
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_candidate
from app.auth.schemas.current_user import CurrentUser
from app.db.models.enums import UserType
from app.db.session import get_session

JOBS_PATH = "/api/v1/jobs"


@pytest.fixture
def offline_client(application: FastAPI, client: TestClient) -> Iterator[TestClient]:
    # The search would fail on this placeholder, so a 422 proves it never ran.
    application.dependency_overrides[get_session] = lambda: object()
    application.dependency_overrides[require_candidate] = lambda: CurrentUser(
        id=uuid4(), user_type=UserType.CANDIDATE
    )
    yield client
    application.dependency_overrides.clear()


@pytest.mark.parametrize(
    ("params", "field"),
    [
        ({"limit": 0}, "query.limit"),
        ({"limit": 101}, "query.limit"),
        ({"limit": "many"}, "query.limit"),
        ({"offset": -1}, "query.offset"),
        ({"offset": 2**63}, "query.offset"),
        ({"search": "a" * 151}, "query.search"),
    ],
    ids=[
        "limit-zero",
        "limit-above-max",
        "limit-not-a-number",
        "negative-offset",
        "offset-above-bigint",
        "long-search",
    ],
)
def test_invalid_query_is_rejected_before_searching(
    offline_client: TestClient, params: dict[str, str | int], field: str
) -> None:
    response = offline_client.get(JOBS_PATH, params=params)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert list(response.json()["errors"]) == [field]
