from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Job, JobSkill, Skill
from app.db.models.enums import SkillType
from tests.jobs.conftest import (
    MANAGE_JOBS_OTHER_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


def edit_path(job_id: object) -> str:
    return f"/api/v1/jobs/{job_id}"


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "title": "Manage Jobs Updated Title",
        "description": "Updated synthetic description.",
        "skills": [{"name": "Manage Jobs Python", "type": SkillType.HARD.value}],
    }
    payload.update(overrides)
    return payload


def test_owner_can_edit_title_description_and_skills(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.patch(
        edit_path(manage_jobs_scenario.open_job_id),
        json=valid_payload(
            skills=[{"name": "Manage Jobs Leadership", "type": SkillType.SOFT.value}]
        ),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Manage Jobs Updated Title"
    assert body["description"] == "Updated synthetic description."
    assert [skill["name"] for skill in body["skills"]] == ["Manage Jobs Leadership"]

    job = database_session.get(Job, manage_jobs_scenario.open_job_id)
    assert job is not None
    assert job.title == "Manage Jobs Updated Title"
    linked_skill_names = database_session.scalars(
        select(Skill.name)
        .join(JobSkill, JobSkill.skill_id == Skill.id)
        .where(JobSkill.job_id == job.id)
    ).all()
    assert linked_skill_names == ["Manage Jobs Leadership"]


def test_title_and_skills_are_required(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        edit_path(manage_jobs_scenario.open_job_id),
        json={"description": "Missing required fields.", "skills": []},
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "validation_error"
    assert "body.title" in response.json()["errors"]
    assert "body.skills" in response.json()["errors"]


def test_a_nonexistent_job_is_not_found(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        edit_path(uuid4()),
        json=valid_payload(),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"


def test_a_company_cannot_edit_another_companys_job(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    response = manage_jobs_client.patch(
        edit_path(manage_jobs_scenario.other_company_job_id),
        json=valid_payload(),
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
    job = database_session.get(Job, manage_jobs_scenario.other_company_job_id)
    assert job is not None
    assert job.title == "Manage Jobs Foreign Role"


def test_unauthenticated_request_is_rejected(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        edit_path(manage_jobs_scenario.open_job_id), json=valid_payload()
    )

    assert response.status_code == 401


def test_another_companys_token_cannot_edit_the_owners_job(
    manage_jobs_client: TestClient, manage_jobs_scenario: ManageJobsScenario
) -> None:
    response = manage_jobs_client.patch(
        edit_path(manage_jobs_scenario.open_job_id),
        json=valid_payload(),
        headers=manage_jobs_authorization(MANAGE_JOBS_OTHER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
