from uuid import UUID

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth.dependencies import (
    get_current_user,
    require_administrator,
    require_approved_company,
    require_candidate,
)
from app.auth.schemas.current_user import CurrentUser
from app.db.models.enums import CompanyStatus, UserType
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider

USER_ID = UUID("22222222-2222-4222-8222-222222222222")

# One guarded route per environment, with the failure code each one answers.
ENVIRONMENTS = {
    "candidate": (require_candidate, "candidate_required"),
    "administrator": (require_administrator, "administrator_required"),
    "company": (require_approved_company, "approved_company_required"),
}


@pytest.fixture
def guarded_application(application: FastAPI) -> FastAPI:
    """Mount one protected route per environment on the real application.

    The product routes these guards will protect belong to the registration and
    administration features, so this exercises the guards over real HTTP without
    inventing a domain endpoint here.
    """
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider
    for name, (guard, _code) in ENVIRONMENTS.items():
        application.get(f"/test-{name}", dependencies=[Depends(guard)])(
            lambda: {"ok": True}
        )
    return application


def sign_in_as(
    application: FastAPI,
    user_type: UserType,
    company_status: CompanyStatus | None = None,
) -> None:
    """Answer as an authenticated account without reaching PostgreSQL.

    The database-backed lookup has its own integration coverage. What matters
    here is the decision each guard makes once the role is known.
    """
    application.dependency_overrides[get_current_user] = lambda: CurrentUser(
        id=USER_ID, user_type=user_type, company_status=company_status
    )


@pytest.mark.parametrize(
    ("user_type", "company_status", "environment"),
    [
        (UserType.CANDIDATE, None, "candidate"),
        (UserType.ADMINISTRATOR, None, "administrator"),
        (UserType.COMPANY, CompanyStatus.APPROVED, "company"),
    ],
)
def test_each_role_reaches_only_its_own_environment(
    guarded_application: FastAPI,
    client: TestClient,
    user_type: UserType,
    company_status: CompanyStatus | None,
    environment: str,
) -> None:
    sign_in_as(guarded_application, user_type, company_status)

    for name, (_guard, code) in ENVIRONMENTS.items():
        response = client.get(f"/test-{name}")
        if name == environment:
            assert response.status_code == 200
            continue
        # Typing another environment's URL is refused with its own stable code.
        assert response.status_code == 403
        assert response.json()["code"] == code


@pytest.mark.parametrize(
    "company_status",
    [None, CompanyStatus.PENDING, CompanyStatus.REJECTED, CompanyStatus.BLOCKED],
)
def test_a_company_that_is_not_approved_stays_out_of_the_company_environment(
    guarded_application: FastAPI,
    client: TestClient,
    company_status: CompanyStatus | None,
) -> None:
    sign_in_as(guarded_application, UserType.COMPANY, company_status)

    response = client.get("/test-company")

    assert response.status_code == 403
    assert response.json()["code"] == "approved_company_required"


@pytest.mark.parametrize("environment", list(ENVIRONMENTS))
def test_a_request_without_a_session_is_refused_before_any_role_check(
    guarded_application: FastAPI, client: TestClient, environment: str
) -> None:
    response = client.get(f"/test-{environment}")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_access_token"
    assert response.headers["WWW-Authenticate"] == "Bearer"
