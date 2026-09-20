import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import Application
from app.db.models.enums import ApplicationStatus
from app.db.session import get_session_factory
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


def withdraw_path(application_id: object) -> str:
    return f"/api/v1/applications/{application_id}/withdraw"


def test_owner_can_withdraw_an_active_application(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(scenario.application_active_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == str(scenario.application_active_id)
    assert body["status"] == "withdrawn"
    with get_session_factory()() as session:
        application = session.get(Application, scenario.application_active_id)
        assert application is not None
        assert application.status == ApplicationStatus.WITHDRAWN
        assert application.closed_at is not None


def test_withdrawal_is_irreversible(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    first = applications_client.post(
        withdraw_path(scenario.application_active_id),
        headers=authorization(OWNER_TOKEN),
    )
    assert first.status_code == 200

    second = applications_client.post(
        withdraw_path(scenario.application_active_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert second.status_code == 409
    assert second.json()["code"] == "application_already_closed"


def test_already_closed_application_is_a_conflict(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(scenario.application_withdrawn_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_closed"


def test_not_selected_application_is_a_conflict(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(scenario.application_not_selected_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_closed"


def test_another_candidates_application_is_not_found_and_left_unchanged(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(scenario.application_other_candidate_id),
        headers=authorization(OWNER_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"
    with get_session_factory()() as session:
        application = session.get(Application, scenario.application_other_candidate_id)
        assert application is not None
        assert application.status == ApplicationStatus.APPLIED
        assert application.candidate_id == scenario.other_id


def test_owner_cannot_withdraw_using_the_other_candidates_token(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(scenario.application_active_id),
        headers=authorization(OTHER_TOKEN),
    )

    assert response.status_code == 404
    with get_session_factory()() as session:
        application = session.get(Application, scenario.application_active_id)
        assert application is not None
        assert application.status == ApplicationStatus.APPLIED


def test_nonexistent_application_is_not_found(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(
        withdraw_path(uuid4()), headers=authorization(OWNER_TOKEN)
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"


def test_unauthenticated_request_is_rejected(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    response = applications_client.post(withdraw_path(scenario.application_active_id))

    assert response.status_code == 401
    with get_session_factory()() as session:
        application = session.get(Application, scenario.application_active_id)
        assert application is not None
        assert application.status == ApplicationStatus.APPLIED


def test_concurrent_withdrawals_only_succeed_once(
    applications_client: TestClient, scenario: ApplicationsScenario
) -> None:
    def submit(_: int) -> int:
        return applications_client.post(
            withdraw_path(scenario.application_on_already_applied_job_id),
            headers=authorization(OWNER_TOKEN),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = sorted(executor.map(submit, range(2)))

    assert outcomes == [200, 409]
    with get_session_factory()() as session:
        application = session.get(
            Application, scenario.application_on_already_applied_job_id
        )
        assert application is not None
        assert application.status == ApplicationStatus.WITHDRAWN
        assert (
            session.scalar(
                select(Application.closed_at).where(
                    Application.id == scenario.application_on_already_applied_job_id
                )
            )
            is not None
        )
