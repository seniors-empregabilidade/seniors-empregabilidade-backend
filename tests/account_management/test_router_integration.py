from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    Address,
    Application,
    AppUser,
    Company,
    Education,
    Event,
    Experience,
    Job,
    Resume,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import AccountStatus, JobStatus, SkillType, WorkMode
from tests.account_management.conftest import (
    ADMIN_TOKEN,
    BLOCKED_TOKEN,
    CANDIDATE_TOKEN,
    AccountManagementScenario,
    authorization,
)

pytestmark = pytest.mark.integration

LIST_PATH = "/api/v1/admin/accounts"
JUSTIFICATION = "Synthetic justification."


def _list(client: TestClient, **params: str | int) -> dict[str, Any]:
    response = client.get(LIST_PATH, params=params, headers=authorization(ADMIN_TOKEN))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body: dict[str, Any] = response.json()
    return body


def _scenario_ids(scenario: AccountManagementScenario) -> set[str]:
    return {
        str(account_id)
        for account_id in (
            scenario.complete_candidate_id,
            scenario.partial_candidate_id,
            scenario.no_resume_candidate_id,
            scenario.blocked_candidate_id,
            scenario.pending_company_id,
            scenario.approved_company_id,
        )
    }


def _listed(
    client: TestClient, scenario: AccountManagementScenario, **params: str | int
) -> set[str]:
    body = _list(client, limit=100, **params)
    return {item["id"] for item in body["items"]} & _scenario_ids(scenario)


def _change_status(
    client: TestClient,
    account_id: UUID,
    status: str,
    reason: str = JUSTIFICATION,
    token: str = ADMIN_TOKEN,
) -> Any:
    return client.patch(
        f"{LIST_PATH}/{account_id}/status",
        json={"status": status, "reason": reason},
        headers=authorization(token),
    )


def test_candidate_detail_fills_the_registration_modal(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    scenario = account_management_scenario
    resume = database_session.scalar(
        select(Resume).where(Resume.candidate_id == scenario.complete_candidate_id)
    )
    assert resume is not None
    resume.summary = "Synthetic summary for the registration modal."
    resume.completion_percentage = 70
    current = Experience(
        resume_id=resume.id,
        company_name="Synthetic Logistics",
        role="Operations Lead",
        start_date=date(2012, 1, 1),
        end_date=date(2023, 12, 1),
    )
    earlier = Experience(
        resume_id=resume.id,
        company_name="Synthetic Logistics",
        role="Operations Supervisor",
        start_date=date(2004, 1, 1),
        end_date=date(2012, 1, 1),
    )
    education = Education(
        resume_id=resume.id,
        institution="Synthetic Institute",
        degree="MBA",
        field="Operations",
        start_date=date(2009, 1, 1),
        end_date=date(2011, 12, 1),
    )
    leadership = Skill(
        name="Account Modal Leadership",
        normalized_name="account modal leadership",
        type=SkillType.SOFT,
    )
    logistics = Skill(
        name="Account Modal Logistics",
        normalized_name="account modal logistics",
        type=SkillType.HARD,
    )
    database_session.add_all((current, earlier, education, leadership, logistics))
    database_session.flush()
    database_session.add_all(
        (
            ResumeSkill(resume_id=resume.id, skill_id=leadership.id),
            ResumeSkill(resume_id=resume.id, skill_id=logistics.id),
        )
    )
    closing = date.today() + timedelta(days=30)
    for title in ("Synthetic Modal Role A", "Synthetic Modal Role B"):
        job = Job(
            company_id=scenario.approved_company_id,
            title=title,
            description="Synthetic role for the registration modal.",
            work_mode=WorkMode.REMOTE,
            status=JobStatus.PUBLISHED,
            closing_date=closing,
        )
        database_session.add(job)
        database_session.flush()
        database_session.add(
            Application(candidate_id=scenario.complete_candidate_id, job_id=job.id)
        )
    database_session.flush()

    response = account_management_client.get(
        f"{LIST_PATH}/{scenario.complete_candidate_id}",
        headers=authorization(ADMIN_TOKEN),
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {
        "id",
        "user_type",
        "email",
        "display_name",
        "account_status",
        "company_status",
        "completion_percentage",
        "created_at",
        "application_count",
        "summary",
        "experiences",
        "education",
        "skills",
        "legal_name",
        "trade_name",
        "cnpj",
        "corporate_email",
        "city",
        "state",
        "industry",
        "company_size",
        "published_job_count",
    }
    assert body["legal_name"] is None
    assert body["trade_name"] is None
    assert body["cnpj"] is None
    assert body["corporate_email"] is None
    assert body["city"] is None
    assert body["state"] is None
    assert body["industry"] is None
    assert body["company_size"] is None
    assert body["published_job_count"] is None
    assert body["display_name"] == "Account Complete Candidate"
    assert body["account_status"] == "active"
    assert body["company_status"] is None
    assert body["completion_percentage"] == 70
    assert body["application_count"] == 2
    assert body["summary"] == "Synthetic summary for the registration modal."
    assert [item["role"] for item in body["experiences"]] == [
        "Operations Lead",
        "Operations Supervisor",
    ]
    assert body["experiences"][0]["company_name"] == "Synthetic Logistics"
    assert body["experiences"][0]["start_date"] == "2012-01-01"
    assert body["experiences"][0]["end_date"] == "2023-12-01"
    assert body["education"] == [
        {
            "id": str(education.id),
            "institution": "Synthetic Institute",
            "degree": "MBA",
            "field": "Operations",
            "start_date": "2009-01-01",
            "end_date": "2011-12-01",
        }
    ]
    assert [item["name"] for item in body["skills"]] == [
        "Account Modal Leadership",
        "Account Modal Logistics",
    ]
    assert "cpf" not in body
    assert "phone" not in body


def test_a_candidate_without_a_resume_still_opens_the_modal(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    response = account_management_client.get(
        f"{LIST_PATH}/{account_management_scenario.no_resume_candidate_id}",
        headers=authorization(ADMIN_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["account_status"] == "active"
    assert body["completion_percentage"] == 0
    assert body["application_count"] == 0
    assert body["summary"] is None
    assert body["experiences"] == []
    assert body["education"] == []
    assert body["skills"] == []


def test_a_blocked_candidate_stays_readable_so_it_can_be_reactivated(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    response = account_management_client.get(
        f"{LIST_PATH}/{account_management_scenario.blocked_candidate_id}",
        headers=authorization(ADMIN_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["account_status"] == "blocked"
    assert response.json()["display_name"] == "Account Blocked Candidate"


def test_company_detail_fills_the_registration_modal(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    scenario = account_management_scenario
    company = database_session.get(Company, scenario.pending_company_id)
    assert company is not None
    address = Address(
        street="Synthetic Street",
        number="100",
        neighborhood="Synthetic District",
        city="Porto Alegre",
        state="RS",
        zip_code="90000000",
    )
    database_session.add(address)
    database_session.flush()
    company.trade_name = "Pending Trade"
    company.industry = "Logistics"
    company.company_size = "11-50"
    company.address_id = address.id
    closing = date.today() + timedelta(days=30)
    for title, status in (
        ("Synthetic Published Role", JobStatus.PUBLISHED),
        ("Synthetic Other Published Role", JobStatus.PUBLISHED),
        ("Synthetic Draft Role", JobStatus.DRAFT),
    ):
        database_session.add(
            Job(
                company_id=company.id,
                title=title,
                description="Synthetic role for the company modal.",
                work_mode=WorkMode.REMOTE,
                status=status,
                closing_date=closing,
            )
        )
    database_session.flush()

    response = account_management_client.get(
        f"{LIST_PATH}/{scenario.pending_company_id}",
        headers=authorization(ADMIN_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["user_type"] == "company"
    assert body["display_name"] == "Pending Trade"
    assert body["legal_name"] == "Account Pending Company"
    assert body["trade_name"] == "Pending Trade"
    assert body["cnpj"] == "90000000000001"
    assert body["corporate_email"] == "account-pending@company.example.invalid"
    assert body["city"] == "Porto Alegre"
    assert body["state"] == "RS"
    assert body["industry"] == "Logistics"
    assert body["company_size"] == "11-50"
    assert body["company_status"] == "pending"
    assert body["published_job_count"] == 2
    assert body["completion_percentage"] is None
    assert body["application_count"] is None
    assert body["summary"] is None
    assert body["experiences"] == []
    assert body["education"] == []
    assert body["skills"] == []
    assert "primary_cnae" not in body
    assert "linkedin_url" not in body
    assert "street" not in body


def test_administrators_and_unknown_accounts_have_no_detail(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    for account_id in (account_management_scenario.administrator_id, uuid4()):
        response = account_management_client.get(
            f"{LIST_PATH}/{account_id}", headers=authorization(ADMIN_TOKEN)
        )

        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        assert response.json()["code"] == "account_not_found"


def test_non_administrators_cannot_read_a_registration(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    response = account_management_client.get(
        f"{LIST_PATH}/{account_management_scenario.complete_candidate_id}",
        headers=authorization(CANDIDATE_TOKEN),
    )

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"


def test_lists_candidates_and_companies_but_never_administrators(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    body = _list(account_management_client, limit=100)

    ids = {item["id"] for item in body["items"]}
    assert _scenario_ids(account_management_scenario) <= ids
    assert str(account_management_scenario.administrator_id) not in ids
    assert {item["user_type"] for item in body["items"]} <= {"candidate", "company"}
    assert body["total"] >= 6


def test_summaries_expose_only_what_an_administrator_needs(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    body = _list(account_management_client, limit=100)
    items = {item["id"]: item for item in body["items"]}

    candidate = items[str(account_management_scenario.partial_candidate_id)]
    company = items[str(account_management_scenario.pending_company_id)]
    assert candidate["email"] == "account-partial@candidate.example.invalid"
    assert candidate["display_name"] == "Account Partial Candidate"
    assert candidate["account_status"] == "active"
    assert candidate["company_status"] is None
    assert candidate["completion_percentage"] == 40
    assert company["display_name"] == "Account Pending Company"
    assert company["company_status"] == "pending"
    assert company["completion_percentage"] is None
    assert set(candidate) == {
        "id",
        "user_type",
        "email",
        "display_name",
        "account_status",
        "company_status",
        "completion_percentage",
        "created_at",
    }


def test_a_candidate_without_a_resume_counts_as_zero_percent_complete(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    body = _list(account_management_client, limit=100)
    items = {item["id"]: item for item in body["items"]}

    bare = items[str(account_management_scenario.no_resume_candidate_id)]
    assert bare["completion_percentage"] == 0


def test_filters_by_account_type(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario

    assert _listed(account_management_client, scenario, user_type="company") == {
        str(scenario.pending_company_id),
        str(scenario.approved_company_id),
    }
    assert _listed(
        account_management_client, scenario, user_type="candidate"
    ) == _scenario_ids(scenario) - {
        str(scenario.pending_company_id),
        str(scenario.approved_company_id),
    }


def test_filters_by_account_status(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario

    assert _listed(account_management_client, scenario, account_status="blocked") == {
        str(scenario.blocked_candidate_id)
    }
    assert str(scenario.blocked_candidate_id) not in _listed(
        account_management_client, scenario, account_status="active"
    )


def test_filters_by_company_situation(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario

    assert _listed(account_management_client, scenario, company_status="pending") == {
        str(scenario.pending_company_id)
    }
    assert _listed(account_management_client, scenario, company_status="approved") == {
        str(scenario.approved_company_id)
    }


def test_filters_by_resume_completion(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario

    assert _listed(account_management_client, scenario, min_completion=100) == {
        str(scenario.complete_candidate_id)
    }
    assert _listed(
        account_management_client, scenario, min_completion=1, max_completion=99
    ) == {str(scenario.partial_candidate_id)}
    assert _listed(account_management_client, scenario, max_completion=0) == {
        str(scenario.no_resume_candidate_id),
        str(scenario.blocked_candidate_id),
    }


def test_filters_combine(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario

    assert _listed(
        account_management_client,
        scenario,
        user_type="candidate",
        account_status="active",
        max_completion=50,
    ) == {str(scenario.partial_candidate_id), str(scenario.no_resume_candidate_id)}
    assert (
        _listed(
            account_management_client,
            scenario,
            user_type="company",
            min_completion=0,
        )
        == set()
    )


def test_paginates_with_a_stable_order_and_the_full_total(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    first = _list(account_management_client, user_type="candidate", limit=2)
    second = _list(account_management_client, user_type="candidate", limit=2, offset=2)
    everything = _list(account_management_client, user_type="candidate", limit=100)

    assert len(first["items"]) == 2
    assert first["total"] == second["total"] == everything["total"]
    assert first["items"] + second["items"] == everything["items"][:4]
    created = [item["created_at"] for item in everything["items"]]
    assert created == sorted(created, reverse=True)


def test_blocking_an_account_logs_the_administrative_action(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    scenario = account_management_scenario

    response = _change_status(
        account_management_client,
        scenario.approved_company_id,
        "blocked",
        reason="  Synthetic abuse report.  ",
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "id": str(scenario.approved_company_id),
        "account_status": "blocked",
    }
    database_session.expire_all()
    account = database_session.get(AppUser, scenario.approved_company_id)
    assert account is not None
    assert account.account_status == AccountStatus.BLOCKED
    events = database_session.scalars(
        select(Event).where(Event.user_id == scenario.administrator_id)
    ).all()
    assert len(events) == 1
    assert events[0].event_type == "account_blocked"
    assert events[0].details == {
        "target_user_id": str(scenario.approved_company_id),
        "previous_status": "active",
        "new_status": "blocked",
        "reason": "Synthetic abuse report.",
    }
    assert _listed(account_management_client, scenario, account_status="blocked") == {
        str(scenario.approved_company_id),
        str(scenario.blocked_candidate_id),
    }


def test_reactivating_an_account_logs_the_administrative_action(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    scenario = account_management_scenario

    response = _change_status(
        account_management_client, scenario.blocked_candidate_id, "active"
    )

    assert response.status_code == 200
    assert response.json() == {
        "id": str(scenario.blocked_candidate_id),
        "account_status": "active",
    }
    database_session.expire_all()
    events = database_session.scalars(
        select(Event).where(Event.user_id == scenario.administrator_id)
    ).all()
    assert [event.event_type for event in events] == ["account_reactivated"]
    assert events[0].details == {
        "target_user_id": str(scenario.blocked_candidate_id),
        "previous_status": "blocked",
        "new_status": "active",
        "reason": JUSTIFICATION,
    }


def test_blocking_takes_effect_immediately_and_reactivation_restores_access(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    scenario = account_management_scenario
    notifications = "/api/v1/notifications/me"
    headers = authorization(CANDIDATE_TOKEN)

    assert (
        account_management_client.get(notifications, headers=headers).status_code == 200
    )

    _change_status(account_management_client, scenario.complete_candidate_id, "blocked")
    blocked = account_management_client.get(notifications, headers=headers)
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "account_unavailable"

    _change_status(account_management_client, scenario.complete_candidate_id, "active")
    assert (
        account_management_client.get(notifications, headers=headers).status_code == 200
    )


def test_an_account_blocked_beforehand_is_rejected_by_authentication(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    response = account_management_client.get(
        "/api/v1/notifications/me", headers=authorization(BLOCKED_TOKEN)
    )

    assert response.status_code == 403
    assert response.json()["code"] == "account_unavailable"


@pytest.mark.parametrize(
    ("scenario_field", "status", "code"),
    [
        ("blocked_candidate_id", "blocked", "account_already_blocked"),
        ("pending_company_id", "active", "account_already_active"),
    ],
)
def test_repeating_a_status_is_a_conflict_that_logs_nothing(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
    scenario_field: str,
    status: str,
    code: str,
) -> None:
    account_id = getattr(account_management_scenario, scenario_field)

    response = _change_status(account_management_client, account_id, status)

    assert response.status_code == 409
    assert response.json()["code"] == code
    database_session.expire_all()
    assert (
        database_session.scalars(
            select(Event).where(
                Event.user_id == account_management_scenario.administrator_id
            )
        ).all()
        == []
    )


def test_administrators_and_unknown_accounts_cannot_be_targeted(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
) -> None:
    for account_id in (account_management_scenario.administrator_id, uuid4()):
        response = _change_status(account_management_client, account_id, "blocked")

        assert response.status_code == 404
        assert response.json()["code"] == "account_not_found"


def test_non_administrators_cannot_change_a_status(
    account_management_client: TestClient,
    account_management_scenario: AccountManagementScenario,
    database_session: Session,
) -> None:
    scenario = account_management_scenario

    response = _change_status(
        account_management_client,
        scenario.approved_company_id,
        "blocked",
        token=CANDIDATE_TOKEN,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "administrator_required"
    database_session.expire_all()
    account = database_session.get(AppUser, scenario.approved_company_id)
    assert account is not None
    assert account.account_status == AccountStatus.ACTIVE
