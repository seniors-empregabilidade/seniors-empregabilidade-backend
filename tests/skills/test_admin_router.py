from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Skill
from app.db.models.enums import SkillType, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

ADMIN_PATH = "/api/v1/admin/skills"
PUBLIC_PATH = "/api/v1/skills"
ADMIN = {"Authorization": "Bearer administrator"}
CANDIDATE = {"Authorization": "Bearer candidate"}
# A shared marker keeps the assertions independent from skills already stored.
MARKER = "Zz Synthetic"


class CatalogIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in ("administrator", "candidate"):
            raise InvalidAccessTokenError
        return f"catalog-{token}"


@pytest.fixture
def catalog_client(
    application: FastAPI, database_session: Session
) -> Iterator[TestClient]:
    database_session.add_all(
        [
            AppUser(
                email="catalog@administrator.example.invalid",
                identity_subject="catalog-administrator",
                user_type=UserType.ADMINISTRATOR,
            ),
            AppUser(
                email="catalog@candidate.example.invalid",
                identity_subject="catalog-candidate",
                user_type=UserType.CANDIDATE,
            ),
            Skill(
                name=f"{MARKER} Excel",
                normalized_name="zz synthetic excel",
                type=SkillType.HARD,
            ),
            Skill(
                name=f"{MARKER} Escuta ativa",
                normalized_name="zz synthetic escuta ativa",
                type=SkillType.SOFT,
                is_active=False,
            ),
        ]
    )
    # Committed so a rolled-back request does not take the scenario with it; the
    # fixture still discards everything at the end.
    database_session.commit()
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = CatalogIdentityProvider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def listed(client: TestClient, **params: str | int) -> dict[str, Any]:
    response = client.get(
        ADMIN_PATH, params={"search": MARKER, **params}, headers=ADMIN
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body: dict[str, Any] = response.json()
    return body


def skill_id(client: TestClient, name: str) -> str:
    items = listed(client)["items"]
    return str(next(item["id"] for item in items if item["name"] == name))


def test_the_list_includes_inactive_skills_sorted_by_name(
    catalog_client: TestClient,
) -> None:
    body = listed(catalog_client)

    assert body["total"] == 2
    assert [(item["name"], item["status"]) for item in body["items"]] == [
        (f"{MARKER} Escuta ativa", "inactive"),
        (f"{MARKER} Excel", "active"),
    ]


def test_the_list_filters_by_type_and_status(catalog_client: TestClient) -> None:
    assert [item["name"] for item in listed(catalog_client, type="hard")["items"]] == [
        f"{MARKER} Excel"
    ]
    inactive = listed(catalog_client, status="inactive")
    assert inactive["total"] == 1
    assert inactive["items"][0]["name"] == f"{MARKER} Escuta ativa"


def test_the_total_counts_every_match_beyond_the_page(
    catalog_client: TestClient,
) -> None:
    body = listed(catalog_client, limit=1, offset=1)

    assert body["total"] == 2
    assert [item["name"] for item in body["items"]] == [f"{MARKER} Excel"]


def test_an_inactive_skill_leaves_the_public_catalog(
    catalog_client: TestClient,
) -> None:
    response = catalog_client.get(
        PUBLIC_PATH, params={"search": MARKER}, headers=CANDIDATE
    )

    assert [skill["name"] for skill in response.json()] == [f"{MARKER} Excel"]


def test_a_created_skill_is_active_and_suggested(catalog_client: TestClient) -> None:
    response = catalog_client.post(
        ADMIN_PATH,
        json={"name": f"  {MARKER}   Power   BI ", "type": "hard"},
        headers=ADMIN,
    )

    assert response.status_code == 201
    assert response.json()["name"] == f"{MARKER} Power BI"
    assert response.json()["status"] == "active"
    suggested = catalog_client.get(
        PUBLIC_PATH, params={"search": "power bi"}, headers=CANDIDATE
    )
    assert [skill["name"] for skill in suggested.json()] == [f"{MARKER} Power BI"]


@pytest.mark.parametrize(
    "name", [f"{MARKER} EXCEL", f"{MARKER} escuta ATIVA", "zz synthétic excel"]
)
def test_a_name_the_catalog_has_in_any_status_conflicts(
    catalog_client: TestClient, name: str
) -> None:
    response = catalog_client.post(
        ADMIN_PATH, json={"name": name, "type": "soft"}, headers=ADMIN
    )

    assert response.status_code == 409
    assert response.json()["code"] == "skill_name_conflict"


def test_editing_renames_and_reclassifies(catalog_client: TestClient) -> None:
    excel = skill_id(catalog_client, f"{MARKER} Excel")

    response = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}",
        json={"name": f"{MARKER} Excel avançado", "type": "soft"},
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": excel,
        "name": f"{MARKER} Excel avançado",
        "type": "soft",
        "status": "active",
    }


def test_fixing_the_accents_of_its_own_name_is_not_a_conflict(
    catalog_client: TestClient,
) -> None:
    excel = skill_id(catalog_client, f"{MARKER} Excel")

    response = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}",
        json={"name": f"{MARKER} Éxcel", "type": "hard"},
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json()["name"] == f"{MARKER} Éxcel"


def test_renaming_to_another_skill_conflicts_and_changes_nothing(
    catalog_client: TestClient, database_session: Session
) -> None:
    excel = skill_id(catalog_client, f"{MARKER} Excel")

    response = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}",
        json={"name": f"{MARKER} Escuta ativa", "type": "hard"},
        headers=ADMIN,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "skill_name_conflict"
    assert database_session.scalar(
        select(Skill.name).where(Skill.normalized_name == "zz synthetic excel")
    ) == (f"{MARKER} Excel")


def test_inactivating_and_reactivating_toggles_the_public_catalog(
    catalog_client: TestClient,
) -> None:
    excel = skill_id(catalog_client, f"{MARKER} Excel")

    inactivated = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}", json={"status": "inactive"}, headers=ADMIN
    )
    again = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}", json={"status": "inactive"}, headers=ADMIN
    )
    public = catalog_client.get(
        PUBLIC_PATH, params={"search": MARKER}, headers=CANDIDATE
    )

    assert inactivated.json()["status"] == "inactive"
    assert again.status_code == 200
    assert public.json() == []

    reactivated = catalog_client.patch(
        f"{ADMIN_PATH}/{excel}", json={"status": "active"}, headers=ADMIN
    )
    assert reactivated.json()["status"] == "active"


def test_an_unknown_skill_is_not_found(catalog_client: TestClient) -> None:
    response = catalog_client.patch(
        f"{ADMIN_PATH}/00000000-0000-4000-8000-000000000000",
        json={"status": "inactive"},
        headers=ADMIN,
    )

    assert response.status_code == 404
    assert response.json()["code"] == "skill_not_found"


@pytest.mark.parametrize(
    "body", [{}, {"status": "deleted"}, {"name": "   "}, {"color": "blue"}]
)
def test_an_update_that_changes_nothing_valid_is_rejected(
    catalog_client: TestClient, body: dict[str, str]
) -> None:
    excel = skill_id(catalog_client, f"{MARKER} Excel")

    response = catalog_client.patch(f"{ADMIN_PATH}/{excel}", json=body, headers=ADMIN)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_a_skill_needs_a_type_to_be_created(catalog_client: TestClient) -> None:
    response = catalog_client.post(
        ADMIN_PATH, json={"name": f"{MARKER} Sem tipo"}, headers=ADMIN
    )

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("method", "path"),
    [("get", ADMIN_PATH), ("post", ADMIN_PATH), ("patch", f"{ADMIN_PATH}/x")],
)
def test_only_administrators_manage_the_catalog(
    catalog_client: TestClient, method: str, path: str
) -> None:
    response = catalog_client.request(
        method, path, json={"name": "x", "type": "hard"}, headers=CANDIDATE
    )
    anonymous = catalog_client.request(method, path)

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"
    assert anonymous.status_code == 401
