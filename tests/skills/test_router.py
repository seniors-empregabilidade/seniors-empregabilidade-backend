from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AppUser, Skill
from app.db.models.enums import SkillType, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

SKILLS_PATH = "/api/v1/skills"
# A shared marker keeps the assertions independent from skills already stored.
MARKER = "Synthetic"
CATALOG = [
    (f"{MARKER} Excel Avançado", "synthetic excel avancado", SkillType.HARD),
    (f"{MARKER} Gestão de equipes", "synthetic gestao de equipes", SkillType.SOFT),
    (f"{MARKER} NR-11", "synthetic nr-11", SkillType.HARD),
]


class SkillIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token != "candidate":
            raise InvalidAccessTokenError
        return "skill-candidate"


@pytest.fixture
def identity_provider() -> SkillIdentityProvider:
    return SkillIdentityProvider()


@pytest.fixture
def catalog(database_session: Session) -> None:
    database_session.add(
        AppUser(
            email="viewer@candidate.example.invalid",
            identity_subject="skill-candidate",
            user_type=UserType.CANDIDATE,
        )
    )
    database_session.add_all(
        Skill(name=name, normalized_name=normalized_name, type=skill_type)
        for name, normalized_name, skill_type in CATALOG
    )
    database_session.flush()


@pytest.fixture
def skills_client(
    application: FastAPI,
    database_session: Session,
    identity_provider: SkillIdentityProvider,
    catalog: None,
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: identity_provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def authorized(client: TestClient, **params: str | int) -> list[dict[str, str]]:
    response = client.get(
        SKILLS_PATH,
        params=params,
        headers={"Authorization": "Bearer candidate"},
    )

    assert response.status_code == 200
    return list(response.json())


def test_the_catalog_requires_an_authenticated_user(skills_client: TestClient) -> None:
    response = skills_client.get(SKILLS_PATH)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")


def test_suggestions_come_sorted_by_name(skills_client: TestClient) -> None:
    found = authorized(skills_client, search=MARKER)

    assert [skill["name"] for skill in found] == [
        f"{MARKER} Excel Avançado",
        f"{MARKER} Gestão de equipes",
        f"{MARKER} NR-11",
    ]
    assert found[0]["type"] == SkillType.HARD.value
    assert found[0]["id"]


@pytest.mark.parametrize("search", ["gestao", "GESTÃO", " gestão de "])
def test_the_search_ignores_case_accents_and_spacing(
    skills_client: TestClient, search: str
) -> None:
    found = authorized(skills_client, search=search)

    assert [skill["name"] for skill in found] == [f"{MARKER} Gestão de equipes"]


def test_a_search_without_matches_returns_an_empty_list(
    skills_client: TestClient,
) -> None:
    assert authorized(skills_client, search=f"{MARKER} power bi") == []


@pytest.mark.parametrize(
    "search", ["ß" * 60, "a" * 99 + "\N{HORIZONTAL ELLIPSIS}", "Synthetic\x00"]
)
def test_a_search_no_stored_name_could_contain_finds_nothing(
    skills_client: TestClient, search: str
) -> None:
    assert authorized(skills_client, search=search) == []


def test_a_search_made_only_of_accents_lists_the_catalog(
    skills_client: TestClient,
) -> None:
    assert authorized(skills_client, search="\N{ACUTE ACCENT}")


def test_the_limit_bounds_the_suggestions(skills_client: TestClient) -> None:
    assert len(authorized(skills_client, search=MARKER, limit=2)) == 2


@pytest.mark.parametrize("limit", [0, 51])
def test_an_unsupported_limit_is_rejected(
    skills_client: TestClient, limit: int
) -> None:
    response = skills_client.get(
        SKILLS_PATH,
        params={"limit": limit},
        headers={"Authorization": "Bearer candidate"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
