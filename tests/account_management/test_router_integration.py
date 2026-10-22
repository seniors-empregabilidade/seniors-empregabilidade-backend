from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Event
from app.db.models.enums import AccountStatus
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
