from collections.abc import Iterator
from datetime import date, datetime
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Company,
    Education,
    Event,
    Experience,
    Job,
    JobSkill,
    Resume,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    EmploymentStatus,
    JobStatus,
    SkillType,
    UserType,
    WorkMode,
)
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.services.platform_indicators import get_platform_indicators
from tests.identity.fakes import FakeIdentityProvider

pytestmark = pytest.mark.integration
BASE = "/api/v1/indicators"
AUTH = {"Authorization": "Bearer admin"}
CREATED = datetime.fromisoformat("2026-10-01T03:00:00+00:00")


class DashboardIdentity(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"admin", "candidate", "company"}:
            raise InvalidAccessTokenError
        return f"dashboard-{token}"


@pytest.fixture
def scenario(database_session: Session) -> dict[str, UUID]:
    s = database_session
    admin = AppUser(
        email="admin@dashboard.example.invalid",
        identity_subject="dashboard-admin",
        user_type=UserType.ADMINISTRATOR,
    )
    s.add(admin)
    skills = [
        Skill(
            name=f"Dashboard skill {n}",
            normalized_name=f"dashboard skill {n}",
            type=SkillType.HARD,
        )
        for n in range(4)
    ]
    s.add_all(skills)
    s.flush()
    ids: dict[str, UUID] = {"admin": admin.id}
    for index, name in enumerate(("complete", "partial", "unknown", "blocked")):
        user = AppUser(
            email=f"{name}@dashboard.example.invalid",
            identity_subject="dashboard-candidate" if name == "complete" else None,
            user_type=UserType.CANDIDATE,
            account_status=AccountStatus.BLOCKED
            if name == "blocked"
            else AccountStatus.ACTIVE,
            created_at=CREATED,
        )
        s.add(user)
        s.flush()
        s.add(
            Candidate(
                id=user.id,
                full_name=f"Synthetic {name}",
                cpf=f"{index + 100:011d}",
                birth_date=date(1970, 1, 1),
                phone="51999990000",
                city="Synthetic City" if name == "complete" else None,
                state="RS" if name == "complete" else None,
            )
        )
        s.flush()
        ids[name] = user.id
        if name == "unknown":
            continue
        resume = Resume(
            candidate_id=user.id,
            summary="Synthetic résumé",
            employment_status=EmploymentStatus.EMPLOYED
            if name == "complete"
            else EmploymentStatus.UNEMPLOYED,
        )
        s.add(resume)
        s.flush()
        picked = (
            (0,)
            if name == "complete"
            else (1, 2)
            if name == "partial"
            else (0, 1, 2, 3)
        )
        s.add_all(
            [ResumeSkill(resume_id=resume.id, skill_id=skills[i].id) for i in picked]
        )
        if name == "complete":
            s.add(
                Experience(
                    resume_id=resume.id,
                    company_name="Synthetic",
                    role="Synthetic",
                    start_date=date(2000, 1, 1),
                )
            )
            s.add(Education(resume_id=resume.id, institution="Synthetic"))
    for index, name in enumerate(("active", "blocked_company", "pending")):
        user = AppUser(
            email=f"{name}@dashboard-company.example.invalid",
            identity_subject="dashboard-company" if name == "active" else None,
            user_type=UserType.COMPANY,
            account_status=AccountStatus.BLOCKED
            if name == "blocked_company"
            else AccountStatus.ACTIVE,
            created_at=CREATED,
        )
        s.add(user)
        s.flush()
        s.add(
            Company(
                id=user.id,
                legal_name=f"Synthetic {name}",
                cnpj=f"{index + 100:014d}",
                corporate_email=user.email,
                status=CompanyStatus.PENDING
                if name == "pending"
                else CompanyStatus.APPROVED,
            )
        )
        s.flush()
        ids[name] = user.id
    for name, company, status, closing, required in [
        ("first", "active", JobStatus.PUBLISHED, date(2099, 1, 1), (0, 1, 2, 3)),
        ("second", "active", JobStatus.PUBLISHED, date(2099, 1, 1), (0, 3)),
        ("closed", "active", JobStatus.CLOSED, date(2099, 1, 1), (0,)),
        ("expired", "active", JobStatus.PUBLISHED, date(2000, 1, 1), (0,)),
        ("blocked_job", "blocked_company", JobStatus.PUBLISHED, date(2099, 1, 1), (0,)),
        ("pending_job", "pending", JobStatus.PUBLISHED, date(2099, 1, 1), (0,)),
    ]:
        job = Job(
            company_id=ids[company],
            title=f"Synthetic {name}",
            description="Synthetic",
            work_mode=WorkMode.REMOTE,
            status=status,
            closing_date=closing,
            created_at=CREATED,
        )
        s.add(job)
        s.flush()
        s.add_all([JobSkill(job_id=job.id, skill_id=skills[i].id) for i in required])
        ids[name] = job.id
    s.add_all(
        [
            Application(
                candidate_id=ids["complete"],
                job_id=ids["first"],
                status=ApplicationStatus.APPLIED,
                match_score=99,
                created_at=CREATED,
            ),
            Application(
                candidate_id=ids["partial"],
                job_id=ids["second"],
                status=ApplicationStatus.HIRED,
                created_at=CREATED,
            ),
        ]
    )
    s.commit()
    return ids


@pytest.fixture
def dashboard_client(
    application: FastAPI, database_session: Session, scenario: dict[str, UUID]
) -> Iterator[TestClient]:
    application.dependency_overrides[get_session] = lambda: database_session
    application.dependency_overrides[get_identity_provider] = DashboardIdentity
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client


def test_dashboard_counts_real_rows_and_live_matches(
    dashboard_client: TestClient,
) -> None:
    response = dashboard_client.get(BASE, headers=AUTH)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json()["totals"] == {
        "candidates": 4,
        "companies": 3,
        "jobs": 6,
        "applications": 2,
        "matches": 2,
    }
    assert response.json()["segments"] == {
        "candidates_without_placement": 2,
        "candidates_with_unknown_employment": 1,
        "incomplete_resumes": 3,
    }


def test_matches_do_not_require_applications_or_trust_stored_scores(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    database_session.execute(delete(Application))
    database_session.commit()
    result = dashboard_client.get(BASE, headers=AUTH).json()
    assert result["totals"]["applications"] == 0
    assert result["totals"]["matches"] == 2
    database_session.add(
        Application(
            candidate_id=scenario["unknown"],
            job_id=scenario["first"],
            match_score=0,
        )
    )
    database_session.commit()
    result = dashboard_client.get(BASE, headers=AUTH).json()
    assert result["totals"]["applications"] == 1
    assert result["totals"]["matches"] == 2


@pytest.mark.parametrize("summary", ["Synthetic résumé", " \t\n", "\u00a0", "\u2003"])
def test_completeness_agrees_with_us08_despite_stale_percentages(
    dashboard_client: TestClient,
    database_session: Session,
    scenario: dict[str, UUID],
    summary: str,
) -> None:
    complete = database_session.scalar(
        select(Resume).where(Resume.candidate_id == scenario["complete"])
    )
    partial = database_session.scalar(
        select(Resume).where(Resume.candidate_id == scenario["partial"])
    )
    assert complete is not None and partial is not None
    complete.summary = summary
    complete.completion_percentage = 0
    partial.completion_percentage = 100
    database_session.commit()
    result = dashboard_client.get(BASE, headers=AUTH).json()
    us08 = dashboard_client.get(
        "/api/v1/professionals", headers=AUTH, params={"completeness": "incomplete"}
    )
    assert us08.status_code == 200
    expected = 3 if summary.strip() else 4
    assert len(us08.json()) == expected
    assert result["segments"]["incomplete_resumes"] == expected


def test_maximum_date_is_supported_without_overflow(
    dashboard_client: TestClient,
) -> None:
    response = dashboard_client.get(
        BASE, headers=AUTH, params={"end_date": "9999-12-31"}
    )
    assert response.status_code == 200
    assert response.json()["filters"]["end_date"] == "9999-12-31"
    assert response.json()["totals"]["candidates"] == 4


def test_company_and_availability_filters_restrict_the_eligible_pairs(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    candidate = database_session.get(Candidate, scenario["partial"])
    assert candidate is not None
    candidate.availability = AvailabilityStatus.UNAVAILABLE
    database_session.commit()
    result = dashboard_client.get(
        BASE,
        headers=AUTH,
        params={
            "candidate_availability": "unavailable",
            "company_status": "approved",
            "application_status": "hired",
        },
    ).json()
    assert result["totals"]["candidates"] == 1
    assert result["totals"]["matches"] == 1
    assert result["totals"]["applications"] == 1
    pending = dashboard_client.get(
        BASE, headers=AUTH, params={"company_status": "pending"}
    ).json()
    assert pending["totals"]["companies"] == 1
    assert pending["totals"]["matches"] == 0


def test_a_blocked_administrator_cannot_read_the_indicators(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    administrator = database_session.get(AppUser, scenario["admin"])
    assert administrator is not None
    administrator.account_status = AccountStatus.BLOCKED
    database_session.commit()
    response = dashboard_client.get(BASE, headers=AUTH)
    assert response.status_code == 403
    assert response.json()["code"] == "account_unavailable"


def test_status_filters_apply_to_their_indicators(dashboard_client: TestClient) -> None:
    result = dashboard_client.get(
        BASE,
        headers=AUTH,
        params={
            "account_status": "blocked",
            "job_status": "closed",
            "application_status": "hired",
        },
    ).json()
    assert result["totals"]["candidates"] == 1
    assert result["totals"]["companies"] == 1
    assert result["totals"]["jobs"] == 1
    assert result["totals"]["applications"] == 1
    assert result["totals"]["matches"] == 0
    assert result["segments"]["candidates_without_placement"] == 1


def test_block_and_reactivation_update_matches_access_and_audit(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    candidate_headers = {"Authorization": "Bearer candidate"}
    assert (
        dashboard_client.get("/api/v1/auth/me", headers=candidate_headers).status_code
        == 200
    )
    path = f"/api/v1/admin/accounts/{scenario['complete']}/status"
    for status, expected_matches, expected_access in (
        ("blocked", 1, 403),
        ("active", 2, 200),
    ):
        response = dashboard_client.patch(
            path,
            headers=AUTH,
            json={"status": status, "reason": "Synthetic account verification."},
        )
        assert response.status_code == 200
        assert (
            dashboard_client.get(BASE, headers=AUTH).json()["totals"]["matches"]
            == expected_matches
        )
        access = dashboard_client.get("/api/v1/auth/me", headers=candidate_headers)
        assert access.status_code == expected_access
        if expected_access == 403:
            assert access.json()["code"] == "account_unavailable"
    events = database_session.scalars(
        select(Event)
        .where(Event.user_id == scenario["admin"])
        .order_by(Event.created_at)
    ).all()
    assert [event.event_type for event in events] == [
        "account_blocked",
        "account_reactivated",
    ]
    for event in events:
        assert event.details is not None
        assert event.details["target_user_id"] == str(scenario["complete"])
        assert event.details["reason"] == "Synthetic account verification."


def test_matches_exclude_jobs_without_requirements(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    database_session.add(
        Job(
            company_id=scenario["active"],
            title="Synthetic role without requirements",
            description="Synthetic",
            work_mode=WorkMode.REMOTE,
            status=JobStatus.PUBLISHED,
            closing_date=date(2099, 1, 1),
        )
    )
    database_session.commit()
    result = dashboard_client.get(BASE, headers=AUTH).json()
    assert result["totals"]["jobs"] == 7
    assert result["totals"]["matches"] == 2


def test_match_threshold_uses_the_exact_ratio_without_integer_rounding(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    skills = [
        Skill(
            name=f"Boundary skill {index}",
            normalized_name=f"boundary skill {index}",
            type=SkillType.HARD,
        )
        for index in range(97)
    ]
    database_session.add_all(skills)
    database_session.flush()
    resume = database_session.scalar(
        select(Resume).where(Resume.candidate_id == scenario["partial"])
    )
    assert resume is not None
    database_session.add_all(
        [JobSkill(job_id=scenario["first"], skill_id=skill.id) for skill in skills]
    )
    database_session.add_all(
        [ResumeSkill(resume_id=resume.id, skill_id=skill.id) for skill in skills[:48]]
    )
    database_session.commit()
    # 50/101 is 49.50%, so rounding to a whole percentage must not count it.
    assert dashboard_client.get(BASE, headers=AUTH).json()["totals"]["matches"] == 1
    database_session.add(ResumeSkill(resume_id=resume.id, skill_id=skills[48].id))
    database_session.commit()
    assert dashboard_client.get(BASE, headers=AUTH).json()["totals"]["matches"] == 2


def test_a_job_remains_open_until_its_closing_day_ends_in_brazil(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    job = database_session.get(Job, scenario["second"])
    assert job is not None
    job.closing_date = date(2026, 10, 24)
    database_session.commit()
    before = get_platform_indicators(
        database_session,
        IndicatorFilters(),
        now=datetime.fromisoformat("2026-10-25T02:59:59+00:00"),
    )
    after = get_platform_indicators(
        database_session,
        IndicatorFilters(),
        now=datetime.fromisoformat("2026-10-25T03:00:00+00:00"),
    )
    assert before.totals.matches == 2
    assert after.totals.matches == 1


def test_period_uses_inclusive_brazil_calendar_days(
    dashboard_client: TestClient, database_session: Session, scenario: dict[str, UUID]
) -> None:
    user = database_session.get(AppUser, scenario["complete"])
    assert user is not None
    user.created_at = datetime.fromisoformat("2026-10-01T02:59:59+00:00")
    database_session.commit()
    result = dashboard_client.get(
        BASE,
        headers=AUTH,
        params={"start_date": "2026-10-01", "end_date": "2026-10-01"},
    ).json()
    assert result["totals"]["candidates"] == 3
    assert result["totals"]["matches"] == 1
    assert result["totals"]["jobs"] == 6
    empty = dashboard_client.get(
        BASE, headers=AUTH, params={"start_date": "2099-12-31"}
    ).json()
    assert not any(empty["totals"].values())
    assert not any(empty["segments"].values())


def test_dashboard_enforces_roles(dashboard_client: TestClient) -> None:
    assert dashboard_client.get(BASE).status_code == 401
    for token in ("candidate", "company"):
        response = dashboard_client.get(
            BASE, headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403
        assert response.json()["code"] == "administrator_required"


@pytest.mark.parametrize(
    "query",
    [
        {"start_date": "2026-10-02", "end_date": "2026-10-01"},
        {"start_date": "invalid"},
        {"account_status": "invalid"},
        {"job_status": "invalid"},
        {"application_status": "invalid"},
    ],
)
def test_invalid_filters_fail_with_problem_details(
    dashboard_client: TestClient, query: dict[str, str]
) -> None:
    response = dashboard_client.get(BASE, headers=AUTH, params=query)
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
