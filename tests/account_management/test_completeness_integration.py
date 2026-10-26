from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Candidate, Education, Experience, Resume, ResumeSkill, Skill
from app.db.models.enums import SkillType
from tests.account_management.conftest import (
    ADMIN_TOKEN,
    AccountManagementScenario,
    authorization,
)

pytestmark = pytest.mark.integration
PATH = "/api/v1/admin/accounts"


@pytest.mark.parametrize("summary", ["Synthetic summary", " \t\n", "\u00a0", "\u2003"])
def test_completeness_agrees_with_us08_instead_of_the_old_percentage(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
    summary: str,
) -> None:
    identifier = account_management_scenario.partial_candidate_id
    candidate = database_session.get(Candidate, identifier)
    resume = database_session.scalar(
        select(Resume).where(Resume.candidate_id == identifier)
    )
    assert candidate is not None and resume is not None
    candidate.city, candidate.state = "Synthetic", "RS"
    resume.summary, resume.completion_percentage = summary, 0
    skill = Skill(
        name="Completeness test",
        normalized_name="completeness test",
        type=SkillType.HARD,
    )
    database_session.add(skill)
    database_session.flush()
    database_session.add_all(
        [
            ResumeSkill(resume_id=resume.id, skill_id=skill.id),
            Experience(
                resume_id=resume.id,
                company_name="Synthetic",
                role="Synthetic",
                start_date=date(2000, 1, 1),
            ),
            Education(resume_id=resume.id, institution="Synthetic"),
        ]
    )
    database_session.commit()
    auth = authorization(ADMIN_TOKEN)
    for completeness in ("complete", "incomplete"):
        response = account_management_client.get(
            PATH, params={"completeness": completeness}, headers=auth
        )
        assert response.status_code == 200
        items = response.json()["items"]
        us08 = account_management_client.get(
            "/api/v1/professionals",
            params={"completeness": completeness},
            headers=auth,
        )
        assert us08.status_code == 200
        assert {row["id"] for row in items} == {row["id"] for row in us08.json()}
        assert response.json()["total"] == len(items)
        assert all(
            bool(row["missing_fields"]) == (completeness == "incomplete")
            for row in items
        )
        for item in items:
            detail = account_management_client.get(f"{PATH}/{item['id']}", headers=auth)
            assert detail.status_code == 200
            assert detail.json()["missing_fields"] == item["missing_fields"]
        if completeness == "complete" and summary.strip():
            assert [row["id"] for row in items] == [str(identifier)]
            assert items[0]["completion_percentage"] == 0


def test_invalid_completeness_returns_problem_details(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    response = account_management_client.get(
        PATH,
        params={"completeness": "invalid"},
        headers=authorization(ADMIN_TOKEN),
    )
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"


def test_completeness_excludes_companies_and_no_resume_is_incomplete(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    auth = authorization(ADMIN_TOKEN)
    company_id = account_management_scenario.approved_company_id
    detail = account_management_client.get(f"{PATH}/{company_id}", headers=auth)
    assert detail.status_code == 200
    assert detail.json()["missing_fields"] is None
    companies = account_management_client.get(
        PATH,
        headers=auth,
        params={"user_type": "company", "completeness": "incomplete"},
    )
    assert companies.status_code == 200
    assert companies.json() == {"items": [], "total": 0}
    incomplete = account_management_client.get(
        PATH, headers=auth, params={"completeness": "incomplete", "limit": 1}
    )
    assert incomplete.status_code == 200
    assert incomplete.json()["total"] == 4
    assert len(incomplete.json()["items"]) == 1
    bare = account_management_client.get(
        f"{PATH}/{account_management_scenario.no_resume_candidate_id}", headers=auth
    )
    assert bare.json()["missing_fields"] == [
        "city",
        "state",
        "summary",
        "experiences",
        "education",
        "skills",
    ]
