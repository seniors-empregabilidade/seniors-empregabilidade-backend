from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_administrator
from app.auth.schemas.current_user import CurrentUser
from app.core.errors import ProblemException
from app.db.models.enums import UserType
from app.db.session import get_session

INDICATORS_PATH = "/api/v1/indicators"
EXPORT_PATH = f"{INDICATORS_PATH}/export"


@pytest.fixture
def as_administrator(application: FastAPI) -> None:
    application.dependency_overrides[require_administrator] = lambda: CurrentUser(
        id=uuid4(), user_type=UserType.ADMINISTRATOR
    )
    application.dependency_overrides[get_session] = lambda: None


def _deny_access() -> None:
    raise ProblemException(
        status_code=403,
        title="Forbidden",
        code="administrator_required",
        detail="An administrator account is required.",
    )


@pytest.mark.parametrize("path", [INDICATORS_PATH, EXPORT_PATH])
def test_indicators_route_is_guarded_by_the_administrator_check(
    application: FastAPI, client: TestClient, path: str
) -> None:
    application.dependency_overrides[require_administrator] = _deny_access
    application.dependency_overrides[get_session] = lambda: None

    response = client.get(path)

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"


@pytest.mark.usefixtures("as_administrator")
@pytest.mark.parametrize("path", [INDICATORS_PATH, EXPORT_PATH])
def test_period_starting_after_it_ends_is_rejected(
    client: TestClient, path: str
) -> None:
    response = client.get(
        path,
        params={"start_date": "2026-02-01", "end_date": "2026-01-01"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_period"


@pytest.mark.usefixtures("as_administrator")
@pytest.mark.parametrize(
    "parameter",
    [
        "account_status",
        "candidate_availability",
        "company_status",
        "job_status",
        "application_status",
    ],
)
def test_unknown_status_value_is_rejected(client: TestClient, parameter: str) -> None:
    response = client.get(INDICATORS_PATH, params={parameter: "not_a_status"})

    assert response.status_code == 422


@pytest.mark.usefixtures("as_administrator")
def test_malformed_date_is_rejected(client: TestClient) -> None:
    response = client.get(INDICATORS_PATH, params={"start_date": "yesterday"})

    assert response.status_code == 422
