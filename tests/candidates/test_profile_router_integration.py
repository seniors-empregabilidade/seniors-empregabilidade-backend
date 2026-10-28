import os
from collections.abc import Iterator
from datetime import date

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select

from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.enums import UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

PROFILE_PATH = "/api/v1/professionals/me"
EMAIL = "profile-router@candidate.example.invalid"
SUBJECT = "profile-router-subject"
AUTH = {"Authorization": "Bearer access"}


@pytest.fixture
def provider(application: FastAPI) -> FakeIdentityProvider:
    fake = FakeIdentityProvider()
    fake.subject = SUBJECT
    application.dependency_overrides[get_identity_provider] = lambda: fake
    return fake


@pytest.fixture(autouse=True)
def clean_rows() -> Iterator[None]:
    yield
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.email == EMAIL))


def add_candidate() -> None:
    with get_session_factory().begin() as session:
        user = AppUser(
            email=EMAIL, identity_subject=SUBJECT, user_type=UserType.CANDIDATE
        )
        session.add(user)
        session.flush()
        session.add(
            Candidate(
                id=user.id,
                full_name="Marcos Silveira",
                cpf="52998224725",
                birth_date=date(1968, 3, 15),
                phone="51999990000",
                city="São Paulo",
                state="SP",
            )
        )


def stored_city() -> str | None:
    with get_session_factory()() as session:
        return session.scalar(
            select(Candidate.city)
            .join(AppUser, AppUser.id == Candidate.id)
            .where(AppUser.email == EMAIL)
        )


def test_patch_is_persisted(client: TestClient, provider: FakeIdentityProvider) -> None:
    add_candidate()

    response = client.patch(PROFILE_PATH, json={"city": "Curitiba"}, headers=AUTH)

    assert response.status_code == 200
    assert stored_city() == "Curitiba"


@pytest.mark.parametrize(
    "field", ["full_name", "phone", "accepts_automatic_application"]
)
def test_required_field_cannot_be_cleared(
    client: TestClient, provider: FakeIdentityProvider, field: str
) -> None:
    add_candidate()

    response = client.patch(PROFILE_PATH, json={field: None}, headers=AUTH)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert f"body.{field}" in response.json()["errors"]


def test_get_after_patch_returns_the_updated_profile(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    patched = client.patch(
        PROFILE_PATH, json={"city": "Curitiba", "state": "pr"}, headers=AUTH
    )
    fetched = client.get(PROFILE_PATH, headers=AUTH)

    assert fetched.status_code == 200
    assert fetched.json() == patched.json()
    assert fetched.json()["city"] == "Curitiba"


def test_profile_exposes_the_candidates_own_missing_fields(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.get(PROFILE_PATH, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["missing_fields"] == [
        "summary",
        "experiences",
        "education",
        "skills",
    ]


def test_profile_requires_a_token(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert client.get(PROFILE_PATH).status_code == 401
    assert client.patch(PROFILE_PATH, json={"city": "Curitiba"}).status_code == 401


def test_profile_is_only_for_candidates(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    with get_session_factory().begin() as session:
        session.add(
            AppUser(email=EMAIL, identity_subject=SUBJECT, user_type=UserType.COMPANY)
        )

    response = client.get(PROFILE_PATH, headers=AUTH)

    assert response.status_code == 403
    assert response.json()["code"] == "candidate_required"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("age", 30),
        ("email", "other@example.com"),
        ("cpf", "11144477735"),
        ("birth_date", "2000-01-01"),
    ],
)
def test_non_editable_fields_are_rejected(
    client: TestClient, provider: FakeIdentityProvider, field: str, value: object
) -> None:
    add_candidate()

    response = client.patch(PROFILE_PATH, json={field: value}, headers=AUTH)

    assert response.status_code == 422
    assert f"body.{field}" in response.json()["errors"]


def test_profile_responses_are_not_cached(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    get_response = client.get(PROFILE_PATH, headers=AUTH)
    patch_response = client.patch(PROFILE_PATH, json={"city": "Curitiba"}, headers=AUTH)

    assert get_response.headers["Cache-Control"] == "no-store"
    assert patch_response.headers["Cache-Control"] == "no-store"


def test_summary_has_a_length_limit(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.patch(PROFILE_PATH, json={"summary": "x" * 2001}, headers=AUTH)

    assert response.status_code == 422
    assert "body.summary" in response.json()["errors"]


def test_profile_has_no_photo_url(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.get(PROFILE_PATH, headers=AUTH)

    assert response.status_code == 200
    assert "photo_url" not in response.json()


def test_automatic_application_can_be_turned_off_and_on(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    # The initial value is the column default, which US-20-T04 turns on, so
    # the test only relies on what the PATCH stores.
    add_candidate()

    turned_off = client.patch(
        PROFILE_PATH, json={"accepts_automatic_application": False}, headers=AUTH
    )
    fetched_off = client.get(PROFILE_PATH, headers=AUTH)
    turned_on = client.patch(
        PROFILE_PATH, json={"accepts_automatic_application": True}, headers=AUTH
    )
    fetched_on = client.get(PROFILE_PATH, headers=AUTH)

    assert turned_off.status_code == 200
    assert turned_off.json()["accepts_automatic_application"] is False
    assert fetched_off.json()["accepts_automatic_application"] is False
    assert turned_on.status_code == 200
    assert turned_on.json()["accepts_automatic_application"] is True
    assert fetched_on.json()["accepts_automatic_application"] is True


def test_other_fields_leave_the_automatic_application_choice_alone(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()
    client.patch(
        PROFILE_PATH, json={"accepts_automatic_application": True}, headers=AUTH
    )

    response = client.patch(PROFILE_PATH, json={"city": "Curitiba"}, headers=AUTH)

    assert response.json()["accepts_automatic_application"] is True


def test_automatic_application_must_be_a_boolean(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.patch(
        PROFILE_PATH, json={"accepts_automatic_application": "maybe"}, headers=AUTH
    )

    assert response.status_code == 422
    assert "body.accepts_automatic_application" in response.json()["errors"]
