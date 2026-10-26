"""Real PostgreSQL flow from candidate application to company decision (US-21)."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Application, Resume, ResumeSkill
from tests.jobs.conftest import (
    MANAGE_JOBS_CANDIDATE_TOKEN,
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)

pytestmark = pytest.mark.integration


@pytest.mark.parametrize("decision", ["hired", "not_selected"])
def test_candidate_sees_each_company_transition_and_final_decision(
    manage_jobs_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    decision: str,
) -> None:
    scenario = manage_jobs_scenario
    database_session.execute(
        delete(Application).where(Application.candidate_id == scenario.candidate_one_id)
    )
    resume = Resume(candidate_id=scenario.candidate_one_id)
    database_session.add(resume)
    database_session.flush()
    database_session.add(ResumeSkill(resume_id=resume.id, skill_id=scenario.skill_id))
    database_session.commit()
    candidate_headers = manage_jobs_authorization(MANAGE_JOBS_CANDIDATE_TOKEN)
    company_headers = manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN)

    submitted = manage_jobs_client.post(
        "/api/v1/applications",
        json={"job_id": str(scenario.open_job_id)},
        headers=candidate_headers,
    )
    assert submitted.status_code == 201
    identifier = submitted.json()["id"]
    assert submitted.json()["matched_requirements"] == 1
    assert submitted.json()["status"] == "under_review"

    listed = manage_jobs_client.get(
        f"/api/v1/jobs/{scenario.open_job_id}/applications", headers=company_headers
    )
    assert listed.status_code == 200
    assert listed.json()["total_applicant_count"] == 2
    assert listed.json()["full_match_count"] == 1
    assert listed.json()["applicants"][0]["application_id"] == identifier
    profile = manage_jobs_client.get(
        f"/api/v1/applications/{identifier}/profile", headers=company_headers
    )
    assert profile.status_code == 200
    assert profile.json()["skills"][0]["id"] == str(scenario.skill_id)

    reason = "Synthetic closing reason." if decision == "not_selected" else None
    for status in ("in_selection_process", decision):
        payload = {"status": status}
        if status == "not_selected":
            payload["reason"] = f"  {reason}  "
        updated = manage_jobs_client.patch(
            f"/api/v1/applications/{identifier}/status",
            json=payload,
            headers=company_headers,
        )
        assert updated.status_code == 200
        visible = manage_jobs_client.get(
            "/api/v1/applications/me", headers=candidate_headers
        )
        assert visible.status_code == 200
        application = next(item for item in visible.json() if item["id"] == identifier)
        assert application["status"] == status
        assert application["reason"] == (reason if status == "not_selected" else None)

    stored = database_session.scalar(
        select(Application).where(Application.candidate_id == scenario.candidate_one_id)
    )
    assert stored is not None
    database_session.refresh(stored)
    assert stored.closed_at is not None
    assert stored.reason == reason
    refused = manage_jobs_client.patch(
        f"/api/v1/applications/{identifier}/status",
        json={"status": "under_review"},
        headers=company_headers,
    )
    assert refused.status_code == 409
    assert refused.json()["code"] == "application_already_closed"
