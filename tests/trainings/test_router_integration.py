from typing import Any
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from tests.trainings.conftest import ADMIN, CANDIDATE, COMPANY

pytestmark = pytest.mark.integration

ADMIN_PATH = "/api/v1/admin/trainings"
PATH = "/api/v1/trainings"
MARKER = "Zz Synthetic"


def add_training(client: TestClient, title: str, **overrides: object) -> str:
    response = client.post(
        ADMIN_PATH,
        json={
            "title": f"{MARKER} {title}",
            "institution": "Escola Sintetica",
            "mode": "remote",
            "external_link": "https://cursos.example.invalid/c",
            **overrides,
        },
        headers=ADMIN,
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def titles(response: Any) -> list[str]:
    assert response.status_code == 200
    return [item["title"] for item in response.json()["items"]]


def test_searching_by_skill_name_ignores_case_and_accents(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    add_training(
        training_client,
        "Planilhas",
        skill_ids=[str(skill_ids["excel"])],
        published=True,
    )
    add_training(
        training_client,
        "Atendimento",
        skill_ids=[str(skill_ids["escuta"])],
        published=True,
    )

    response = training_client.get(
        PATH, params={"skill": "ZZ TRAINING EXCÉL"}, headers=CANDIDATE
    )

    assert titles(response) == [f"{MARKER} Planilhas"]
    assert response.json()["total"] == 1


def test_searching_by_skill_id_finds_exact_matches(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    add_training(
        training_client,
        "Planilhas",
        skill_ids=[str(skill_ids["excel"])],
        published=True,
    )
    add_training(
        training_client,
        "Atendimento",
        skill_ids=[str(skill_ids["escuta"])],
        published=True,
    )

    response = training_client.get(
        PATH, params={"skill_id": str(skill_ids["escuta"])}, headers=COMPANY
    )

    assert titles(response) == [f"{MARKER} Atendimento"]


def test_unpublished_courses_are_never_listed(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    add_training(training_client, "Rascunho", skill_ids=[str(skill_ids["excel"])])

    response = training_client.get(
        PATH, params={"skill_id": str(skill_ids["excel"])}, headers=CANDIDATE
    )

    assert titles(response) == []
    assert response.json()["total"] == 0


def test_the_candidate_view_hides_publication_state_and_jobs(
    training_client: TestClient, skill_ids: dict[str, UUID], job_id: UUID
) -> None:
    add_training(
        training_client,
        "Planilhas",
        skill_ids=[str(skill_ids["excel"])],
        job_ids=[str(job_id)],
        published=True,
    )

    item = training_client.get(
        PATH, params={"skill_id": str(skill_ids["excel"])}, headers=CANDIDATE
    ).json()["items"][0]

    assert set(item) == {
        "id",
        "title",
        "institution",
        "mode",
        "external_link",
        "skills",
    }
    assert item["skills"][0]["name"] == "Zz Training Excel"


def test_a_search_that_matches_no_skill_finds_nothing(
    training_client: TestClient,
) -> None:
    response = training_client.get(
        PATH, params={"skill": "zz no such skill"}, headers=CANDIDATE
    )

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_a_search_no_name_could_contain_finds_nothing(
    training_client: TestClient,
) -> None:
    response = training_client.get(
        PATH, params={"skill": "a\u0000b"}, headers=CANDIDATE
    )

    assert response.json() == {"items": [], "total": 0}


def test_search_parameters_are_validated(training_client: TestClient) -> None:
    for params in (
        {"skill_id": "not-a-uuid"},
        {"limit": 0},
        {"limit": 51},
        {"offset": -1},
        {"skill": "x" * 101},
    ):
        response = training_client.get(PATH, params=params, headers=CANDIDATE)

        assert response.status_code == 422
