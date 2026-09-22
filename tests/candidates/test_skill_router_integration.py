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
from app.db.models.enums import SkillType, UserType
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

SKILLS_PATH = "/api/v1/professionals/me/skills"
PROFILE_PATH = "/api/v1/professionals/me"
EMAIL = "skill-router@candidate.example.invalid"
SUBJECT = "skill-router-subject"
SKILL_NAME = "Lideranca de equipes remotas"
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
        session.execute(delete(Skill).where(Skill.name == SKILL_NAME))


def add_candidate() -> UUID:
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
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1968, 3, 15),
                phone="51999990000",
            )
        )
        return user.id


def add_catalog_skill() -> UUID:
    with get_session_factory().begin() as session:
        skill = Skill(
            name=SKILL_NAME,
            normalized_name=SKILL_NAME.casefold(),
            type=SkillType.SOFT,
        )
        session.add(skill)
        session.flush()
        return skill.id


def linked_skills(user_id: UUID) -> list[UUID]:
    with get_session_factory()() as session:
        resume = session.query(Resume).filter(Resume.candidate_id == user_id).first()
        if resume is None:
            return []
        links = session.query(ResumeSkill).filter(ResumeSkill.resume_id == resume.id)
        return [link.skill_id for link in links]


def test_add_skill_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()

    response = client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    assert response.status_code == 201
    assert response.json() == {
        "id": str(skill_id),
        "name": SKILL_NAME,
        "type": "soft",
    }
    assert linked_skills(user_id) == [skill_id]


def test_profile_returns_skills_as_objects(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()
    skill_id = add_catalog_skill()
    client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    response = client.get(PROFILE_PATH, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["skills"] == [
        {"id": str(skill_id), "name": SKILL_NAME, "type": "soft"}
    ]


def test_unknown_skill_is_rejected(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.post(SKILLS_PATH, json={"skill_id": str(uuid4())}, headers=AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "skill_not_found"


def test_the_same_skill_cannot_be_added_twice(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()
    client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    response = client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    assert response.status_code == 409
    assert response.json()["code"] == "skill_already_added"
    assert linked_skills(user_id) == [skill_id]


def test_remove_skill_keeps_the_catalog_entry(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()
    client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    response = client.delete(f"{SKILLS_PATH}/{skill_id}", headers=AUTH)

    assert response.status_code == 204
    assert linked_skills(user_id) == []
    with get_session_factory()() as session:
        assert session.get(Skill, skill_id) is not None


def test_removing_a_skill_that_is_not_in_the_profile_is_not_found(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()
    skill_id = add_catalog_skill()

    response = client.delete(f"{SKILLS_PATH}/{skill_id}", headers=AUTH)

    assert response.status_code == 404
    assert response.json()["code"] == "skill_not_found"


def test_skills_require_a_token(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert client.post(SKILLS_PATH, json={"skill_id": str(uuid4())}).status_code == 401
