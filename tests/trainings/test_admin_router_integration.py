from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Skill, Training, TrainingJob, TrainingSkill
from tests.trainings.conftest import ADMIN, CANDIDATE, COMPANY

pytestmark = pytest.mark.integration

PATH = "/api/v1/admin/trainings"
MARKER = "Zz Synthetic"


def payload(**overrides: object) -> dict[str, Any]:
    return {
        "title": f"{MARKER} Excel basico",
        "institution": "Escola Sintetica",
        "mode": "online",
        "external_link": "https://cursos.example.invalid/excel",
        **overrides,
    }


def create(client: TestClient, **overrides: object) -> dict[str, Any]:
    response = client.post(PATH, json=payload(**overrides), headers=ADMIN)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


@pytest.mark.parametrize("headers", [CANDIDATE, COMPANY])
def test_only_administrators_manage_the_catalog(
    training_client: TestClient, headers: dict[str, str]
) -> None:
    training_id = uuid4()
    calls = [
        training_client.get(PATH, headers=headers),
        training_client.post(PATH, json=payload(), headers=headers),
        training_client.get(f"{PATH}/{training_id}", headers=headers),
        training_client.patch(
            f"{PATH}/{training_id}", json={"title": "x"}, headers=headers
        ),
        training_client.delete(f"{PATH}/{training_id}", headers=headers),
    ]

    for response in calls:
        assert response.status_code == 403
        assert response.json()["code"] == "administrator_required"


def test_creating_a_course_returns_it_hidden_with_its_relations(
    training_client: TestClient, skill_ids: dict[str, UUID], job_id: UUID
) -> None:
    body = create(
        training_client,
        skill_ids=[str(skill_ids["excel"]), str(skill_ids["escuta"])],
        job_ids=[str(job_id)],
    )

    assert body["title"] == f"{MARKER} Excel basico"
    assert body["institution"] == "Escola Sintetica"
    assert body["mode"] == "online"
    assert body["external_link"] == "https://cursos.example.invalid/excel"
    assert body["published"] is False
    assert [skill["name"] for skill in body["skills"]] == [
        "Zz Training Escuta ativa",
        "Zz Training Excel",
    ]
    assert body["job_ids"] == [str(job_id)]


def test_a_course_can_be_read_back(training_client: TestClient) -> None:
    created = create(training_client)

    response = training_client.get(f"{PATH}/{created['id']}", headers=ADMIN)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == created


def test_an_unknown_course_is_not_found(training_client: TestClient) -> None:
    unknown = uuid4()
    calls = [
        training_client.get(f"{PATH}/{unknown}", headers=ADMIN),
        training_client.patch(f"{PATH}/{unknown}", json={"title": "x"}, headers=ADMIN),
        training_client.delete(f"{PATH}/{unknown}", headers=ADMIN),
    ]

    for response in calls:
        assert response.status_code == 404
        assert response.headers["content-type"].startswith("application/problem+json")
        assert response.json()["code"] == "training_not_found"


def test_an_unknown_skill_or_job_is_refused_and_nothing_is_saved(
    training_client: TestClient, database_session: Session
) -> None:
    before = database_session.scalar(select(func.count()).select_from(Training))
    for field in ("skill_ids", "job_ids"):
        response = training_client.post(
            PATH, json=payload(**{field: [str(uuid4())]}), headers=ADMIN
        )

        assert response.status_code == 422
        assert response.json()["code"] == "training_relation_not_found"
        assert field in response.json()["errors"]

    after = database_session.scalar(select(func.count()).select_from(Training))
    assert after == before


def test_invalid_input_is_a_validation_problem(training_client: TestClient) -> None:
    response = training_client.post(
        PATH, json=payload(external_link="ftp://x.example.invalid"), headers=ADMIN
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_updating_changes_only_the_sent_fields(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    created = create(training_client, skill_ids=[str(skill_ids["excel"])])

    response = training_client.patch(
        f"{PATH}/{created['id']}",
        json={"published": True, "mode": "hybrid"},
        headers=ADMIN,
    )

    assert response.status_code == 200
    assert response.json() == {**created, "published": True, "mode": "hybrid"}


def test_sending_relations_replaces_them_and_an_empty_list_clears_them(
    training_client: TestClient, skill_ids: dict[str, UUID], job_id: UUID
) -> None:
    created = create(
        training_client,
        skill_ids=[str(skill_ids["excel"])],
        job_ids=[str(job_id)],
    )

    replaced = training_client.patch(
        f"{PATH}/{created['id']}",
        json={"skill_ids": [str(skill_ids["escuta"])], "job_ids": []},
        headers=ADMIN,
    ).json()

    assert [skill["id"] for skill in replaced["skills"]] == [str(skill_ids["escuta"])]
    assert replaced["job_ids"] == []


def test_a_failed_update_keeps_the_course_untouched(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    created = create(training_client, skill_ids=[str(skill_ids["excel"])])

    response = training_client.patch(
        f"{PATH}/{created['id']}",
        json={"title": "Changed", "skill_ids": [str(uuid4())]},
        headers=ADMIN,
    )

    assert response.status_code == 422
    unchanged = training_client.get(f"{PATH}/{created['id']}", headers=ADMIN)
    assert unchanged.json() == created


def test_deleting_removes_the_course_and_its_links_but_not_the_skill_or_job(
    training_client: TestClient,
    database_session: Session,
    skill_ids: dict[str, UUID],
    job_id: UUID,
) -> None:
    created = create(
        training_client,
        skill_ids=[str(skill_ids["excel"])],
        job_ids=[str(job_id)],
    )

    response = training_client.delete(f"{PATH}/{created['id']}", headers=ADMIN)

    assert response.status_code == 204
    assert response.content == b""
    assert (
        training_client.get(f"{PATH}/{created['id']}", headers=ADMIN).status_code == 404
    )
    for model in (TrainingSkill, TrainingJob):
        assert database_session.scalar(select(func.count()).select_from(model)) == 0
    assert database_session.get(Skill, skill_ids["excel"]) is not None


def test_the_list_filters_by_text_skill_and_publication(
    training_client: TestClient, skill_ids: dict[str, UUID]
) -> None:
    create(
        training_client,
        title=f"{MARKER} Planilhas",
        skill_ids=[str(skill_ids["excel"])],
        published=True,
    )
    create(training_client, title=f"{MARKER} Atendimento", institution="Outra Escola")

    everything = training_client.get(PATH, params={"search": MARKER}, headers=ADMIN)
    by_skill = training_client.get(
        PATH, params={"skill_id": str(skill_ids["excel"])}, headers=ADMIN
    )
    published = training_client.get(
        PATH, params={"search": MARKER, "published": "true"}, headers=ADMIN
    )
    by_institution = training_client.get(
        PATH, params={"search": "outra escola"}, headers=ADMIN
    )

    assert everything.headers["cache-control"] == "no-store"
    assert everything.json()["total"] == 2
    assert [item["title"] for item in everything.json()["items"]] == [
        f"{MARKER} Atendimento",
        f"{MARKER} Planilhas",
    ]
    assert [item["title"] for item in by_skill.json()["items"]] == [
        f"{MARKER} Planilhas"
    ]
    assert published.json()["total"] == 1
    assert by_institution.json()["total"] == 1


def test_the_list_is_paginated(training_client: TestClient) -> None:
    for number in range(3):
        create(training_client, title=f"{MARKER} Curso {number}")

    response = training_client.get(
        PATH, params={"search": MARKER, "limit": 2, "offset": 2}, headers=ADMIN
    )

    assert response.json()["total"] == 3
    assert [item["title"] for item in response.json()["items"]] == [f"{MARKER} Curso 2"]
