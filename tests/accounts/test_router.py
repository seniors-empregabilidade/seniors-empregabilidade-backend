import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.accounts.exceptions import InvalidVerificationCodeError
from app.accounts.router import provide_email_verification_provider
from app.db.models.app_user import AppUser
from app.db.session import get_session
from app.main import create_app
from tests.accounts.conftest import FakeEmailVerificationProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires RUN_DATABASE_INTEGRATION_TESTS=1 and migrated PostgreSQL",
    ),
]

SEND = "/api/v1/email-verification/send"
CONFIRM = "/api/v1/email-verification/confirm"


@pytest.fixture
def client(
    session: Session, provider: FakeEmailVerificationProvider
) -> Iterator[TestClient]:
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    application.dependency_overrides[provide_email_verification_provider] = lambda: (
        provider
    )
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
    application.dependency_overrides.clear()


def test_sending_to_a_known_address_is_accepted(
    client: TestClient,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    response = client.post(SEND, json={"email": unverified_user.email})

    assert response.status_code == 202
    assert response.content == b""
    assert provider.sent_to == [unverified_user.email]


def test_sending_to_an_unknown_address_answers_the_same(
    client: TestClient,
    provider: FakeEmailVerificationProvider,
) -> None:
    response = client.post(SEND, json={"email": "nobody@example.invalid"})

    assert response.status_code == 202
    assert response.content == b""
    assert provider.sent_to == []


def test_a_second_send_inside_the_cooldown_reports_a_stable_code(
    client: TestClient,
    unverified_user: AppUser,
) -> None:
    client.post(SEND, json={"email": unverified_user.email})

    response = client.post(SEND, json={"email": unverified_user.email})

    assert response.status_code == 429
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "verification_resend_too_soon"


def test_confirming_with_an_accepted_code_verifies_the_address(
    client: TestClient,
    session: Session,
    unverified_user: AppUser,
) -> None:
    response = client.post(
        CONFIRM, json={"email": unverified_user.email, "code": "123456"}
    )

    assert response.status_code == 204
    verified_at = session.execute(
        select(AppUser.email_verified_at).where(AppUser.id == unverified_user.id)
    ).scalar_one()
    assert verified_at is not None


def test_a_rejected_code_reports_a_stable_code(
    client: TestClient,
    provider: FakeEmailVerificationProvider,
    unverified_user: AppUser,
) -> None:
    provider.failure = InvalidVerificationCodeError()

    response = client.post(
        CONFIRM, json={"email": unverified_user.email, "code": "000000"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_verification_code"


def test_an_unknown_address_confirms_exactly_like_a_wrong_code(
    client: TestClient,
    unverified_user: AppUser,
) -> None:
    unknown = client.post(
        CONFIRM, json={"email": "nobody@example.invalid", "code": "123456"}
    )

    assert unknown.status_code == 422
    assert unknown.json()["code"] == "invalid_verification_code"


def test_an_unexpected_field_is_rejected(
    client: TestClient,
    unverified_user: AppUser,
) -> None:
    response = client.post(
        SEND, json={"email": unverified_user.email, "role": "administrator"}
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_the_endpoints_are_published_under_the_versioned_prefix(
    client: TestClient,
) -> None:
    paths = client.get("/openapi.json").json()["paths"]

    assert SEND in paths
    assert CONFIRM in paths
