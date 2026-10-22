import os
import time
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text

from app.candidates.schemas.skill_link import SkillSelectionRequest
from app.candidates.services.skills import replace_skills
from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.enums import SkillType, UserType
from app.db.models.resume import Resume
from app.db.models.resume_skill import ResumeSkill
from app.db.models.skill import Skill
from app.db.session import get_engine, get_session_factory
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
OTHER_SKILL_NAME = "Comunicacao com clientes remotos"
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
        session.execute(
            delete(Skill).where(Skill.name.in_([SKILL_NAME, OTHER_SKILL_NAME]))
        )


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


def add_catalog_skill(name: str = SKILL_NAME) -> UUID:
    with get_session_factory().begin() as session:
        skill = Skill(
            name=name,
            normalized_name=name.casefold(),
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


def test_replace_skills_is_persisted(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    replaced = add_catalog_skill()
    chosen = add_catalog_skill(OTHER_SKILL_NAME)
    client.post(SKILLS_PATH, json={"skill_id": str(replaced)}, headers=AUTH)

    response = client.put(SKILLS_PATH, json={"skill_ids": [str(chosen)]}, headers=AUTH)

    assert response.status_code == 200
    assert response.json() == [
        {"id": str(chosen), "name": OTHER_SKILL_NAME, "type": "soft"}
    ]
    assert response.headers["Cache-Control"] == "no-store"
    assert linked_skills(user_id) == [chosen]


def test_replaced_skills_are_returned_sorted_by_name(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    leadership = add_catalog_skill()
    communication = add_catalog_skill(OTHER_SKILL_NAME)

    response = client.put(
        SKILLS_PATH,
        json={"skill_ids": [str(leadership), str(communication)]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert [skill["name"] for skill in response.json()] == [
        OTHER_SKILL_NAME,
        SKILL_NAME,
    ]
    assert set(linked_skills(user_id)) == {leadership, communication}


def test_replacing_with_an_empty_list_clears_the_skills(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()
    client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    response = client.put(SKILLS_PATH, json={"skill_ids": []}, headers=AUTH)

    assert response.status_code == 200
    assert response.json() == []
    assert linked_skills(user_id) == []


def test_replacing_with_an_unknown_skill_changes_nothing(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()
    client.post(SKILLS_PATH, json={"skill_id": str(skill_id)}, headers=AUTH)

    response = client.put(SKILLS_PATH, json={"skill_ids": [str(uuid4())]}, headers=AUTH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "skill_not_found"
    assert linked_skills(user_id) == [skill_id]


def test_a_repeated_skill_is_saved_once(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    user_id = add_candidate()
    skill_id = add_catalog_skill()

    response = client.put(
        SKILLS_PATH,
        json={"skill_ids": [str(skill_id), str(skill_id)]},
        headers=AUTH,
    )

    assert response.status_code == 200
    assert [skill["id"] for skill in response.json()] == [str(skill_id)]
    assert linked_skills(user_id) == [skill_id]


def test_concurrent_first_replacements_are_serialized() -> None:
    user_id = add_candidate()
    first_skill = add_catalog_skill()
    second_skill = add_catalog_skill(OTHER_SKILL_NAME)

    with ThreadPoolExecutor(max_workers=2) as executor:
        with get_engine().begin() as gate:
            gate.execute(
                select(Candidate.id).where(Candidate.id == user_id).with_for_update()
            )
            first = executor.submit(_replace_in_new_session, user_id, first_skill)
            second = executor.submit(_replace_in_new_session, user_id, second_skill)
            _wait_for_replacements_to_block(first, second)

        assert first.result(timeout=10) == first_skill
        assert second.result(timeout=10) == second_skill

    assert linked_skills(user_id) in ([first_skill], [second_skill])


def _replace_in_new_session(user_id: UUID, skill_id: UUID) -> UUID:
    with get_session_factory()() as session:
        result = replace_skills(
            user_id, SkillSelectionRequest(skill_ids=[skill_id]), session=session
        )
        return result[0].id


def _wait_for_replacements_to_block(*workers: Future[UUID]) -> None:
    blocked = text(
        "SELECT count(*) FROM pg_stat_activity "
        "WHERE datname = current_database() "
        "AND cardinality(pg_blocking_pids(pid)) > 0"
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        for worker in workers:
            if worker.done():
                worker.result()
        with get_engine().connect() as connection:
            if connection.scalar(blocked) >= len(workers):
                return
        time.sleep(0.01)
    raise AssertionError("both replacements should wait for the candidate lock")


def test_free_text_skills_are_rejected(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.put(
        SKILLS_PATH,
        json={"skill_ids": ["Ética"]},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_more_than_one_hundred_skills_are_rejected(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    add_candidate()

    response = client.put(
        SKILLS_PATH,
        json={"skill_ids": [str(uuid4()) for _ in range(101)]},
        headers=AUTH,
    )

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "validation_error"


def test_replace_skills_is_only_for_candidates(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    with get_session_factory().begin() as session:
        session.add(
            AppUser(email=EMAIL, identity_subject=SUBJECT, user_type=UserType.COMPANY)
        )

    response = client.put(SKILLS_PATH, json={"skill_ids": []}, headers=AUTH)

    assert response.status_code == 403
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "candidate_required"


def test_skills_require_a_token(
    client: TestClient, provider: FakeIdentityProvider
) -> None:
    assert client.post(SKILLS_PATH, json={"skill_id": str(uuid4())}).status_code == 401
    assert client.put(SKILLS_PATH, json={"skill_ids": []}).status_code == 401
