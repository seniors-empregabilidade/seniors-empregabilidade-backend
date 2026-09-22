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
from app.db.models.education import Education
from app.db.models.enums import UserType
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

EDUCATION_PATH = "/api/v1/professionals/me/education"
EMAIL = "education-router@candidate.example.invalid"
OTHER_EMAIL = "education-other@candidate.example.invalid"
SUBJECT = "education-router-subject"
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
    "institution": "FGV",
    "degree": "MBA em Gestão Empresarial",
    "field": "Gestão",
    "start_date": "2009-01-01",
    "end_date": "2011-12-31",
}


def add_education_row(user_id: UUID) -> UUID:
    with get_session_factory().begin() as session:
        resume = Resume(candidate_id=user_id)
        session.add(resume)
        session.flush()
        education = Education(
            resume_id=resume.id,
            institution="Instituto Antigo",
            degree="Tecnólogo",
            start_date=date(2000, 1, 1),
        )
        session.add(education)
        session.flush()
        return education.id


def stored_education(education_id: UUID) -> Education | None:
    with get_session_factory()() as session:
        return session.get(Education, education_id)


def test_create_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(EDUCATION_PATH, json=VALID_BODY, headers=AUTH)

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    stored = stored_education(UUID(response.json()["id"]))
    assert stored is not None
    assert stored.degree == "MBA em Gestão Empresarial"


def test_only_institution_is_required(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(EDUCATION_PATH, json={"institution": "PUCRS"}, headers=AUTH)

    assert response.status_code == 201
    assert response.json()["degree"] is None


def test_end_date_before_start_date_is_rejected(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(
        EDUCATION_PATH, json={**VALID_BODY, "end_date": "2008-01-01"}, headers=AUTH
    )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_education_period"
    assert "end_date" in response.json()["errors"]


def test_update_changes_only_sent_fields_and_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    education_id = add_education_row(add_candidate())

    response = client.patch(
        f"{EDUCATION_PATH}/{education_id}", json={"field": "Logística"}, headers=AUTH
    )

    assert response.status_code == 200
    assert response.json()["institution"] == "Instituto Antigo"
    stored = stored_education(education_id)
    assert stored is not None
    assert stored.field == "Logística"


def test_optional_field_can_be_cleared(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    education_id = add_education_row(add_candidate())

    response = client.patch(
        f"{EDUCATION_PATH}/{education_id}", json={"degree": None}, headers=AUTH
    )

    assert response.status_code == 200
    stored = stored_education(education_id)
    assert stored is not None
    assert stored.degree is None


def test_institution_cannot_be_cleared(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    education_id = add_education_row(add_candidate())

    response = client.patch(
        f"{EDUCATION_PATH}/{education_id}", json={"institution": None}, headers=AUTH
    )

    assert response.status_code == 422
    assert "body.institution" in response.json()["errors"]


def test_delete_removes_the_education(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    education_id = add_education_row(add_candidate())

    response = client.delete(f"{EDUCATION_PATH}/{education_id}", headers=AUTH)

    assert response.status_code == 204
    assert stored_education(education_id) is None


def test_other_candidates_education_is_not_found(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    other_education = add_education_row(add_candidate(OTHER_EMAIL, "other-subject"))
    add_candidate()
    path = f"{EDUCATION_PATH}/{other_education}"

    patched = client.patch(path, json={"institution": "Invasor"}, headers=AUTH)
    deleted = client.delete(path, headers=AUTH)

    assert patched.status_code == 404
    assert patched.json()["code"] == "education_not_found"
    assert deleted.status_code == 404
    stored = stored_education(other_education)
    assert stored is not None
    assert stored.institution == "Instituto Antigo"


def test_education_requires_a_token(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert client.post(EDUCATION_PATH, json=VALID_BODY).status_code == 401
