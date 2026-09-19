import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.applications.conftest import (
    OTHER_TOKEN,
    OWNER_TOKEN,
    ApplicationsScenario,
    authorization,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

LIST_PATH = "/api/v1/applications/me"


def test_unauthenticated_request_is_rejected(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH)

    assert response.status_code == 401


def test_only_returns_the_authenticated_candidates_applications(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(scenario.application_not_selected_id) in ids
    assert str(scenario.application_active_id) in ids
    assert str(scenario.application_withdrawn_id) in ids
    assert str(scenario.application_on_already_applied_job_id) in ids
    assert str(scenario.application_other_candidate_id) not in ids


def test_other_candidate_only_sees_their_own_application(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OTHER_TOKEN))

    assert response.status_code == 200
    items = response.json()
    assert [item["id"] for item in items] == [
        str(scenario.application_other_candidate_id)
    ]


def test_company_name_filter_is_partial_and_case_insensitive(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(
        LIST_PATH,
        params={"company_name": "aCmE"},
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert str(scenario.application_not_selected_id) in ids
    assert str(scenario.application_withdrawn_id) in ids
    assert str(scenario.application_on_already_applied_job_id) in ids
    assert str(scenario.application_active_id) not in ids


def test_company_name_filter_without_a_match_returns_an_empty_list(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(
        LIST_PATH,
        params={"company_name": "no-such-company-xyz"},
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    assert response.json() == []


def test_days_in_process_for_an_active_application_counts_up_to_today(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    item = _find(response.json(), scenario.application_active_id)
    assert item["status"] == "applied"
    assert item["days_in_process"] == 5


def test_days_in_process_for_a_closed_application_counts_up_to_closing_date(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    item = _find(response.json(), scenario.application_not_selected_id)
    assert item["status"] == "not_selected"
    # submitted 10 days ago, closed 3 days ago: process lasted 7 days, not 10.
    assert item["days_in_process"] == 7


def test_not_selected_application_includes_similar_job_suggestions(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    item = _find(response.json(), scenario.application_not_selected_id)
    suggested_ids = [job["id"] for job in item["similar_jobs"]]

    assert str(scenario.job_similar_strong_id) in suggested_ids
    assert str(scenario.job_similar_weak_id) in suggested_ids
    assert str(scenario.job_no_match_id) not in suggested_ids
    assert str(scenario.job_already_applied_id) not in suggested_ids
    assert str(scenario.job_draft_id) not in suggested_ids
    assert str(scenario.job_target_id) not in suggested_ids
    # More shared skills first.
    assert suggested_ids.index(str(scenario.job_similar_strong_id)) < (
        suggested_ids.index(str(scenario.job_similar_weak_id))
    )
    assert item["closed_reason"] is None


def test_active_application_never_includes_suggestions_or_reason(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    item = _find(response.json(), scenario.application_active_id)
    assert item["similar_jobs"] == []
    assert item["closed_reason"] is None


def test_candidate_withdrawn_application_never_includes_suggestions_or_reason(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.get(LIST_PATH, headers=authorization(OWNER_TOKEN))

    item = _find(response.json(), scenario.application_withdrawn_id)
    assert item["status"] == "withdrawn"
    assert item["similar_jobs"] == []
    assert item["closed_reason"] is None


def _find(items: list[dict[str, Any]], application_id: object) -> dict[str, Any]:
    return next(item for item in items if item["id"] == str(application_id))
