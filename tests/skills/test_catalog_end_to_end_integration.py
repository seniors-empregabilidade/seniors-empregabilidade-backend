"""US-06-T04: the administrator's catalog, the professional's selection and the
compatibility of US-19 working together through the API.

An administrator adds a skill, a professional selects it, a company requires it,
and the compatibility counts it on both sides. Inactivating the skill withdraws it
from selection without breaking the résumés and jobs that already link it.
"""

from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.skills.conftest import (
    ADMIN_TOKEN,
    CANDIDATE_TOKEN,
    COMPANY_TOKEN,
    OTHER_CANDIDATE_TOKEN,
    CatalogFlowActors,
    authorization,
)

pytestmark = pytest.mark.integration

SKILL_NAME = "Catalog Flow Empilhadeira"
JOB_TITLE = "Catalog Flow Operador de empilhadeira"
ADMIN = authorization(ADMIN_TOKEN)
CANDIDATE = authorization(CANDIDATE_TOKEN)
OTHER_CANDIDATE = authorization(OTHER_CANDIDATE_TOKEN)
COMPANY = authorization(COMPANY_TOKEN)


def create_skill(client: TestClient) -> str:
    response = client.post(
        "/api/v1/admin/skills",
        json={"name": SKILL_NAME, "type": "hard"},
        headers=ADMIN,
    )
    assert response.status_code == 201
    skill_id: str = response.json()["id"]
    return skill_id


def change_status(client: TestClient, skill_id: str, status: str) -> None:
    response = client.patch(
        f"/api/v1/admin/skills/{skill_id}", json={"status": status}, headers=ADMIN
    )
    assert response.status_code == 200
    assert response.json()["status"] == status


def suggestions(client: TestClient) -> list[str]:
    response = client.get(
        "/api/v1/skills", params={"search": SKILL_NAME}, headers=CANDIDATE
    )
    assert response.status_code == 200
    return [skill["id"] for skill in response.json()]


def select_skills(
    client: TestClient, skill_ids: list[str], headers: dict[str, str] = CANDIDATE
) -> Any:
    return client.put(
        "/api/v1/professionals/me/skills",
        json={"skill_ids": skill_ids},
        headers=headers,
    )


def profile_skills(
    client: TestClient, headers: dict[str, str] = CANDIDATE
) -> list[dict[str, str]]:
    response = client.get("/api/v1/professionals/me", headers=headers)
    assert response.status_code == 200
    skills: list[dict[str, str]] = response.json()["skills"]
    return skills


def publish_job(client: TestClient) -> str:
    response = client.post(
        "/api/v1/jobs",
        json={
            "title": JOB_TITLE,
            "description": "Synthetic job for the catalog flow.",
            # The company types the name freely; it resolves to the same entry.
            "skills": [{"name": "catalog flow EMPILHADEIRA", "type": "soft"}],
            "work_mode": "onsite",
            "closing_date": (date.today() + timedelta(days=30)).isoformat(),
        },
        headers=COMPANY,
    )
    assert response.status_code == 201
    job_id: str = response.json()["id"]
    return job_id


def ranking(client: TestClient, job_id: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/jobs/{job_id}/applications", headers=COMPANY)
    assert response.status_code == 200
    applicants: list[dict[str, Any]] = response.json()["applicants"]
    return applicants


def candidate_view_of_the_job(client: TestClient) -> dict[str, Any]:
    response = client.get(
        "/api/v1/jobs", params={"search": JOB_TITLE}, headers=CANDIDATE
    )
    assert response.status_code == 200
    [job] = response.json()
    result: dict[str, Any] = job
    return result


def assert_the_skill_counts_in_the_match(
    client: TestClient, *, job_id: str, skill_id: str, candidate_id: UUID
) -> None:
    [match] = ranking(client, job_id)
    assert match["profile"]["candidate_id"] == str(candidate_id)
    assert match["origin"] == "automatic_match"
    assert match["compatibility_percentage"] == "100.00"
    assert match["matched_skills"] == [{"id": skill_id, "name": SKILL_NAME}]
    assert match["missing_skills"] == []

    job = candidate_view_of_the_job(client)
    assert (job["matched_skill_count"], job["required_skill_count"]) == (1, 1)
    assert job["missing_skills"] == []


def test_a_selected_skill_reaches_the_profile_and_the_match(
    catalog_flow_client: TestClient, catalog_flow_actors: CatalogFlowActors
) -> None:
    skill_id = create_skill(catalog_flow_client)
    assert suggestions(catalog_flow_client) == [skill_id]

    selected = select_skills(catalog_flow_client, [skill_id])

    assert selected.status_code == 200
    expected = [{"id": skill_id, "name": SKILL_NAME, "type": "hard"}]
    assert selected.json() == expected
    assert profile_skills(catalog_flow_client) == expected
    job_id = publish_job(catalog_flow_client)
    assert_the_skill_counts_in_the_match(
        catalog_flow_client,
        job_id=job_id,
        skill_id=skill_id,
        candidate_id=catalog_flow_actors.candidate_id,
    )


def test_an_inactive_skill_leaves_the_selection_but_not_existing_profiles(
    catalog_flow_client: TestClient, catalog_flow_actors: CatalogFlowActors
) -> None:
    skill_id = create_skill(catalog_flow_client)
    assert select_skills(catalog_flow_client, [skill_id]).status_code == 200
    job_id = publish_job(catalog_flow_client)

    change_status(catalog_flow_client, skill_id, "inactive")

    assert suggestions(catalog_flow_client) == []
    assert [skill["id"] for skill in profile_skills(catalog_flow_client)] == [skill_id]
    assert_the_skill_counts_in_the_match(
        catalog_flow_client,
        job_id=job_id,
        skill_id=skill_id,
        candidate_id=catalog_flow_actors.candidate_id,
    )
    # Saving the profile again keeps the inactive skill it already had.
    kept = select_skills(catalog_flow_client, [skill_id])
    assert kept.status_code == 200
    assert [skill["id"] for skill in kept.json()] == [skill_id]


def test_an_inactive_skill_cannot_be_selected_anew(
    catalog_flow_client: TestClient, catalog_flow_actors: CatalogFlowActors
) -> None:
    skill_id = create_skill(catalog_flow_client)
    change_status(catalog_flow_client, skill_id, "inactive")

    replaced = select_skills(catalog_flow_client, [skill_id], headers=OTHER_CANDIDATE)
    added = catalog_flow_client.post(
        "/api/v1/professionals/me/skills",
        json={"skill_id": skill_id},
        headers=OTHER_CANDIDATE,
    )

    for response in (replaced, added):
        assert response.status_code == 404
        assert response.json()["code"] == "skill_not_found"
    assert profile_skills(catalog_flow_client, OTHER_CANDIDATE) == []


def test_a_removed_inactive_skill_returns_only_after_reactivation(
    catalog_flow_client: TestClient, catalog_flow_actors: CatalogFlowActors
) -> None:
    skill_id = create_skill(catalog_flow_client)
    assert select_skills(catalog_flow_client, [skill_id]).status_code == 200
    change_status(catalog_flow_client, skill_id, "inactive")
    assert select_skills(catalog_flow_client, []).status_code == 200

    assert select_skills(catalog_flow_client, [skill_id]).status_code == 404

    change_status(catalog_flow_client, skill_id, "active")
    assert suggestions(catalog_flow_client) == [skill_id]
    assert select_skills(catalog_flow_client, [skill_id]).status_code == 200
    assert [skill["id"] for skill in profile_skills(catalog_flow_client)] == [skill_id]
