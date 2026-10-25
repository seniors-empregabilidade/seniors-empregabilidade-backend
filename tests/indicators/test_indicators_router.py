import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import require_administrator
from app.core.errors import ProblemException
from app.db.session import get_session

INDICATORS_PATH = "/api/v1/indicators"


@pytest.fixture
def as_administrator(application: FastAPI) -> None:
    application.dependency_overrides[require_administrator] = lambda: None
    application.dependency_overrides[get_session] = lambda: None


def _deny_access() -> None:
    raise ProblemException(
        status_code=403,
        title="Forbidden",
        code="administrator_required",
        detail="An administrator account is required.",
    )


def test_indicators_route_is_guarded_by_the_administrator_check(
    application: FastAPI, client: TestClient
) -> None:
    application.dependency_overrides[require_administrator] = _deny_access
    application.dependency_overrides[get_session] = lambda: None

    response = client.get(INDICATORS_PATH)

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"


@pytest.mark.usefixtures("as_administrator")
def test_period_starting_after_it_ends_is_rejected(client: TestClient) -> None:
    response = client.get(
        INDICATORS_PATH,
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
