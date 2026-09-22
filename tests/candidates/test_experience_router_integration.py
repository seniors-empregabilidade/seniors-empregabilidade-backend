import os
from collections.abc import Iterator
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.enums import UserType
from app.db.models.experience import Experience
from app.db.models.resume import Resume
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

EXPERIENCES_PATH = "/api/v1/professionals/me/experiences"
EMAIL = "experience-router@candidate.example.invalid"
OTHER_EMAIL = "experience-other@candidate.example.invalid"
SUBJECT = "experience-router-subject"
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
        session.execute(delete(AppUser).where(AppUser.email.in_([EMAIL, OTHER_EMAIL])))


def add_candidate(email: str = EMAIL, subject: str = SUBJECT) -> UUID:
    with get_session_factory().begin() as session:
        user = AppUser(
            email=email, identity_subject=subject, user_type=UserType.CANDIDATE
        )
        session.add(user)
        session.flush()
        session.add(
            Candidate(
                id=user.id,
                full_name="Marcos Silveira",
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1968, 3, 15),
                phone="51999990000",
            )
        )
        return user.id


VALID_BODY = {
    "company_name": "Log Brasil",
    "role": "Gerente de Operações",
    "start_date": "2012-01-01",
    "end_date": "2023-12-31",
}


def add_experience_row(user_id: UUID) -> UUID:
    with get_session_factory().begin() as session:
        resume = Resume(candidate_id=user_id)
        session.add(resume)
        session.flush()
        experience = Experience(
            resume_id=resume.id,
            company_name="Empresa Antiga",
            role="Analista",
            start_date=date(2000, 1, 1),
        )
        session.add(experience)
        session.flush()
        return experience.id


def stored_experience(experience_id: UUID) -> Experience | None:
    with get_session_factory()() as session:
        return session.get(Experience, experience_id)


def test_create_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(EXPERIENCES_PATH, json=VALID_BODY, headers=AUTH)

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    stored = stored_experience(UUID(response.json()["id"]))
    assert stored is not None
    assert stored.company_name == "Log Brasil"


def test_end_date_before_start_date_is_rejected(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(
        EXPERIENCES_PATH, json={**VALID_BODY, "end_date": "2011-01-01"}, headers=AUTH
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_experience_period"
    assert "end_date" in response.json()["errors"]


def test_update_changes_only_sent_fields_and_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    experience_id = add_experience_row(add_candidate())

    response = client.patch(
        f"{EXPERIENCES_PATH}/{experience_id}",
        json={"role": "Coordenador"},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert response.json()["company_name"] == "Empresa Antiga"
    stored = stored_experience(experience_id)
    assert stored is not None
    assert stored.role == "Coordenador"


def test_update_checks_the_period_against_stored_dates(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    experience_id = add_experience_row(add_candidate())

    response = client.patch(
        f"{EXPERIENCES_PATH}/{experience_id}",
        json={"end_date": "1999-01-01"},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert "end_date" in response.json()["errors"]


@pytest.mark.parametrize("field", ["company_name", "role", "start_date"])
def test_required_field_cannot_be_cleared(
    client: TestClient, provider: FakeIdentityProvider, field: str
) -> None:
    experience_id = add_experience_row(add_candidate())

    response = client.patch(
        f"{EXPERIENCES_PATH}/{experience_id}", json={field: None}, headers=AUTH
    )

    assert response.status_code == 422
    assert f"body.{field}" in response.json()["errors"]


def test_delete_removes_the_experience(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    experience_id = add_experience_row(add_candidate())

    response = client.delete(f"{EXPERIENCES_PATH}/{experience_id}", headers=AUTH)

    assert response.status_code == 204
    assert stored_experience(experience_id) is None


def test_other_candidates_experience_is_not_found(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    other_experience = add_experience_row(add_candidate(OTHER_EMAIL, "other-subject"))
    add_candidate()
    path = f"{EXPERIENCES_PATH}/{other_experience}"

    patched = client.patch(path, json={"role": "Invasor"}, headers=AUTH)
    deleted = client.delete(path, headers=AUTH)

    assert patched.status_code == 404
    assert patched.json()["code"] == "experience_not_found"
    assert deleted.status_code == 404
    stored = stored_experience(other_experience)
    assert stored is not None
    assert stored.role == "Analista"


def test_experiences_require_a_token(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert client.post(EXPERIENCES_PATH, json=VALID_BODY).status_code == 401
