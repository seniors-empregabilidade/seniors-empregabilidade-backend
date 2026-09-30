"""Integration tests for PATCH /api/v1/applications/{application_id}/status."""

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import ClassVar
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Company,
    Job,
    JobSkill,
    Skill,
)
from app.db.models.enums import (
    ApplicationStatus,
    CompanyStatus,
    JobStatus,
    SkillType,
    UserType,
    WorkMode,
)
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration

COMPANY_TOKEN = "update-app-status-company"
OTHER_COMPANY_TOKEN = "update-app-status-other-company"


class UpdateAppStatusIdentityProvider(FakeIdentityProvider):
    _SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        COMPANY_TOKEN: "subject-update-app-status-company",
        OTHER_COMPANY_TOKEN: "subject-update-app-status-other",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self._SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def status_path(application_id: object) -> str:
    return f"/api/v1/applications/{application_id}/status"


@pytest.fixture
def update_status_identity_provider() -> UpdateAppStatusIdentityProvider:
    return UpdateAppStatusIdentityProvider()


@pytest.fixture
def update_status_client(
    application: FastAPI,
    database_session: Session,
    update_status_identity_provider: UpdateAppStatusIdentityProvider,
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = lambda: (
        update_status_identity_provider
    )
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


@dataclass(frozen=True, slots=True)
class UpdateStatusScenario:
    company_id: UUID
    other_company_id: UUID
    applied_application_id: UUID
    under_review_application_id: UUID
    in_selection_application_id: UUID
    hired_application_id: UUID
    not_selected_application_id: UUID
    withdrawn_application_id: UUID
    other_company_application_id: UUID


@pytest.fixture
def update_status_scenario(database_session: Session) -> UpdateStatusScenario:
    now = datetime.now(UTC)
    far_future = date.today() + timedelta(days=30)

    company_user = AppUser(
        email="update-app-status-company@company.example.invalid",
        identity_subject=UpdateAppStatusIdentityProvider._SUBJECTS_BY_TOKEN[
            COMPANY_TOKEN
        ],
        user_type=UserType.COMPANY,
    )
    other_company_user = AppUser(
        email="update-app-status-other@company.example.invalid",
        identity_subject=UpdateAppStatusIdentityProvider._SUBJECTS_BY_TOKEN[
            OTHER_COMPANY_TOKEN
        ],
        user_type=UserType.COMPANY,
    )
    candidate_user = AppUser(
        email="update-app-status-candidate@candidate.example.invalid",
        identity_subject=None,
        user_type=UserType.CANDIDATE,
    )
    database_session.add_all((company_user, other_company_user, candidate_user))
    database_session.flush()

    company = Company(
        id=company_user.id,
        cnpj="11444777000161",
        legal_name="Update Status Company",
        corporate_email=company_user.email,
        status=CompanyStatus.APPROVED,
    )
    other_company = Company(
        id=other_company_user.id,
        cnpj="60746948000112",
        legal_name="Update Status Other Company",
        corporate_email=other_company_user.email,
        status=CompanyStatus.APPROVED,
    )
    candidate = Candidate(
        id=candidate_user.id,
        full_name="Update Status Candidate",
        cpf="33366699957",
        birth_date=date(1972, 1, 1),
        phone="+5551999990002",
    )
    skill = Skill(
        name="Update Status Python",
        normalized_name="update status python",
        type=SkillType.HARD,
    )
    database_session.add_all((company, other_company, candidate, skill))
    database_session.flush()

    def _make_job(company_id: UUID, title_suffix: str) -> Job:
        j = Job(
            company_id=company_id,
            title=f"Update Status Role {title_suffix}",
            description="Synthetic role for update-application-status tests.",
            work_mode=WorkMode.REMOTE,
            status=JobStatus.PUBLISHED,
            published_at=now,
            closing_date=far_future,
        )
        database_session.add(j)
        database_session.flush()
        return j

    def _make_app(
        job_id: UUID, status: ApplicationStatus, closed: bool = False
    ) -> Application:
        app = Application(
            candidate_id=candidate.id,
            job_id=job_id,
            status=status,
            closed_at=now - timedelta(days=1) if closed else None,
        )
        database_session.add(app)
        database_session.flush()
        return app

    applied_job = _make_job(company.id, "applied")
    applied_app = _make_app(applied_job.id, ApplicationStatus.APPLIED)
    database_session.add(JobSkill(job_id=applied_job.id, skill_id=skill.id))

    under_review_job = _make_job(company.id, "under_review")
    under_review_app = _make_app(under_review_job.id, ApplicationStatus.UNDER_REVIEW)

    in_selection_job = _make_job(company.id, "in_selection")
    in_selection_app = _make_app(
        in_selection_job.id, ApplicationStatus.IN_SELECTION_PROCESS
    )

    hired_job = _make_job(company.id, "hired")
    hired_app = _make_app(hired_job.id, ApplicationStatus.HIRED, closed=True)

    not_selected_job = _make_job(company.id, "not_selected")
    not_selected_app = _make_app(
        not_selected_job.id, ApplicationStatus.NOT_SELECTED, closed=True
    )

    withdrawn_job = _make_job(company.id, "withdrawn")
    withdrawn_app = _make_app(
        withdrawn_job.id, ApplicationStatus.WITHDRAWN, closed=True
    )

    other_company_job = _make_job(other_company.id, "other_company")
    other_company_app = _make_app(other_company_job.id, ApplicationStatus.APPLIED)

    database_session.commit()

    return UpdateStatusScenario(
        company_id=company.id,
        other_company_id=other_company.id,
        applied_application_id=applied_app.id,
        under_review_application_id=under_review_app.id,
        in_selection_application_id=in_selection_app.id,
        hired_application_id=hired_app.id,
        not_selected_application_id=not_selected_app.id,
        withdrawn_application_id=withdrawn_app.id,
        other_company_application_id=other_company_app.id,
    )


# ──────────────────────────────────────────────
# Happy-path transitions
# ──────────────────────────────────────────────


def test_company_can_move_applied_to_under_review(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "under_review"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "under_review"
    database_session.expire_all()
    app = database_session.get(
        Application, update_status_scenario.applied_application_id
    )
    assert app is not None
    assert app.status == ApplicationStatus.UNDER_REVIEW


def test_company_can_move_under_review_to_in_selection(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.under_review_application_id),
        json={"status": "in_selection_process"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "in_selection_process"


def test_company_can_move_under_review_to_not_selected_with_reason(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.under_review_application_id),
        json={
            "status": "not_selected",
            "reason": "Profile does not match requirements.",
        },
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "not_selected"
    database_session.expire_all()
    app = database_session.get(
        Application, update_status_scenario.under_review_application_id
    )
    assert app is not None
    assert app.status == ApplicationStatus.NOT_SELECTED
    assert app.reason == "Profile does not match requirements."
    assert app.closed_at is not None


def test_company_can_move_in_selection_to_hired(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.in_selection_application_id),
        json={"status": "hired"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "hired"
    database_session.expire_all()
    app = database_session.get(
        Application, update_status_scenario.in_selection_application_id
    )
    assert app is not None
    assert app.closed_at is not None


# ──────────────────────────────────────────────
# Reason validation
# ──────────────────────────────────────────────


def test_not_selected_without_reason_is_rejected(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "not_selected"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 422


def test_reason_is_accepted_for_non_rejection_statuses(
    update_status_client: TestClient,
    database_session: Session,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "under_review", "reason": "Some text"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 200
    assert response.json()["status"] == "under_review"


# ──────────────────────────────────────────────
# Invalid transitions
# ──────────────────────────────────────────────


def test_applied_to_hired_is_not_allowed(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "hired"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_status_transition_not_allowed"


def test_applied_to_in_selection_is_not_allowed(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "in_selection_process"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_status_transition_not_allowed"


# ──────────────────────────────────────────────
# Terminal-status guard
# ──────────────────────────────────────────────


def test_already_hired_application_is_a_conflict(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.hired_application_id),
        json={"status": "not_selected", "reason": "Changing mind."},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_closed"


def test_already_not_selected_application_is_a_conflict(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.not_selected_application_id),
        json={"status": "under_review"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_closed"


def test_withdrawn_application_is_a_conflict(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.withdrawn_application_id),
        json={"status": "under_review"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "application_already_closed"


# ──────────────────────────────────────────────
# Authorization and access control
# ──────────────────────────────────────────────


def test_application_from_another_companys_job_returns_404(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.other_company_application_id),
        json={"status": "under_review"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"


def test_nonexistent_application_returns_404(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(uuid4()),
        json={"status": "under_review"},
        headers=auth(COMPANY_TOKEN),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "application_not_found"


def test_unauthenticated_request_is_rejected(
    update_status_client: TestClient,
    update_status_scenario: UpdateStatusScenario,
) -> None:
    response = update_status_client.patch(
        status_path(update_status_scenario.applied_application_id),
        json={"status": "under_review"},
    )

    assert response.status_code == 401
