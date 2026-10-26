from dataclasses import replace
from datetime import UTC, date, datetime
from itertools import count

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.dependencies import require_administrator
from app.db.models import JobSkill, ResumeSkill, Skill
from app.db.models.app_user import AppUser
from app.db.models.application import Application
from app.db.models.candidate import Candidate
from app.db.models.company import Company
from app.db.models.enums import (
    ApplicationStatus,
    AvailabilityStatus,
    CompanyStatus,
    EmploymentStatus,
    JobStatus,
    SkillType,
    UserType,
    WorkMode,
)
from app.db.models.job import Job
from app.db.models.resume import Resume
from app.db.session import get_session
from app.indicators.schemas.indicator_filters import IndicatorFilters
from app.indicators.services.platform_indicators import get_platform_indicators

INDICATORS_PATH = "/api/v1/indicators"
IN_PERIOD = datetime(2001, 1, 15, 12, tzinfo=UTC)
BEFORE_PERIOD = datetime(2000, 12, 31, 12, tzinfo=UTC)
LAST_SECOND_OF_PERIOD = datetime(2001, 2, 1, 1, 59, 59, 999999, tzinfo=UTC)
FIRST_SECOND_AFTER_PERIOD = datetime(2001, 2, 1, 2, 0, 0, tzinfo=UTC)
PERIOD = IndicatorFilters(start_date=date(2001, 1, 1), end_date=date(2001, 1, 31))

_sequence = count(1)
pytestmark = pytest.mark.integration


def _user(session: Session, user_type: UserType, created_at: datetime) -> AppUser:
    user = AppUser(
        email=f"indicators{next(_sequence)}@indicators.example",
        user_type=user_type,
        created_at=created_at,
        updated_at=created_at,
    )
    session.add(user)
    session.flush()
    return user


def _candidate(
    session: Session,
    *,
    availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
    created_at: datetime = IN_PERIOD,
) -> Candidate:
    user = _user(session, UserType.CANDIDATE, created_at)
    candidate = Candidate(
        id=user.id,
        full_name="Indicators Candidate",
        cpf=f"{90_000_000_000 + next(_sequence):011d}",
        birth_date=date(1960, 1, 1),
        phone="51999990000",
        availability=availability,
    )
    session.add(candidate)
    session.flush()
    return candidate


def _company(session: Session, status: CompanyStatus) -> Company:
    user = _user(session, UserType.COMPANY, IN_PERIOD)
    number = next(_sequence)
    company = Company(
        id=user.id,
        cnpj=f"{80_000_000_000_000 + number:014d}",
        legal_name="Indicators Company",
        corporate_email=f"hr{number}@indicators-company.example",
        status=status,
    )
    session.add(company)
    session.flush()
    return company


def _resume(session: Session, candidate: Candidate, completion: int) -> Resume:
    resume = Resume(
        candidate_id=candidate.id,
        completion_percentage=completion,
        created_at=IN_PERIOD,
        updated_at=IN_PERIOD,
    )
    session.add(resume)
    session.flush()
    return resume


def _job(session: Session, company: Company, status: JobStatus) -> Job:
    job = Job(
        company_id=company.id,
        title="Indicators Job",
        description="Indicators job description",
        work_mode=WorkMode.REMOTE,
        closing_date=date(2099, 2, 28),
        status=status,
        created_at=IN_PERIOD,
        updated_at=IN_PERIOD,
    )
    session.add(job)
    session.flush()
    return job


def _application(
    session: Session,
    candidate: Candidate,
    job: Job,
    status: ApplicationStatus,
    match_score: int | None,
) -> None:
    session.add(
        Application(
            candidate_id=candidate.id,
            job_id=job.id,
            status=status,
            match_score=match_score,
            created_at=IN_PERIOD,
            updated_at=IN_PERIOD,
        )
    )
    session.flush()


def _seed_scenario(session: Session) -> None:
    """Creates 3 candidates, 2 companies, 2 jobs and 3 applications.

    c_hired:   available,   resume 100%, hired on the published job (score 90)
    c_partial: available,   resume 50%,  applied to the published job (score 80)
    c_bare:    unavailable, no resume,   applied to the draft job (no score)
    """
    approved = _company(session, CompanyStatus.APPROVED)
    _company(session, CompanyStatus.PENDING)
    published = _job(session, approved, JobStatus.PUBLISHED)
    draft = _job(session, approved, JobStatus.DRAFT)

    c_hired = _candidate(session)
    hired_resume = _resume(session, c_hired, 100)
    hired_resume.employment_status = EmploymentStatus.EMPLOYED
    c_partial = _candidate(session)
    partial_resume = _resume(session, c_partial, 50)
    partial_resume.employment_status = EmploymentStatus.UNEMPLOYED
    c_bare = _candidate(session, availability=AvailabilityStatus.UNAVAILABLE)

    skills = [
        Skill(
            name=f"Indicator skill {n}",
            normalized_name=f"indicator skill {n}",
            type=SkillType.HARD,
        )
        for n in range(2)
    ]
    session.add_all(skills)
    session.flush()
    session.add_all(
        [
            *[JobSkill(job_id=published.id, skill_id=skill.id) for skill in skills],
            ResumeSkill(resume_id=hired_resume.id, skill_id=skills[0].id),
            ResumeSkill(resume_id=partial_resume.id, skill_id=skills[1].id),
        ]
    )
    session.flush()

    _application(session, c_hired, published, ApplicationStatus.HIRED, 90)
    _application(session, c_partial, published, ApplicationStatus.APPLIED, 80)
    _application(session, c_bare, draft, ApplicationStatus.APPLIED, None)


@pytest.fixture
def seeded(database_session: Session) -> Session:
    _seed_scenario(database_session)
    return database_session


def test_counts_every_entity_in_the_period(seeded: Session) -> None:
    indicators = get_platform_indicators(seeded, PERIOD)

    assert indicators.totals.candidates == 3
    assert indicators.totals.companies == 2
    assert indicators.totals.jobs == 2
    assert indicators.totals.applications == 3
    assert indicators.totals.matches == 2


def test_segments_count_candidates_without_placement_and_incomplete_resumes(
    seeded: Session,
) -> None:
    indicators = get_platform_indicators(seeded, PERIOD)

    assert indicators.segments.candidates_without_placement == 1
    assert indicators.segments.candidates_with_unknown_employment == 1
    assert indicators.segments.incomplete_resumes == 3


def test_records_before_the_period_are_ignored(seeded: Session) -> None:
    _candidate(seeded, created_at=BEFORE_PERIOD)

    indicators = get_platform_indicators(seeded, PERIOD)

    assert indicators.totals.candidates == 3
    assert indicators.segments.incomplete_resumes == 3


def test_period_bounds_include_the_last_day_and_exclude_the_next(
    seeded: Session,
) -> None:
    _candidate(seeded, created_at=LAST_SECOND_OF_PERIOD)
    _candidate(seeded, created_at=FIRST_SECOND_AFTER_PERIOD)

    indicators = get_platform_indicators(seeded, PERIOD)

    assert indicators.totals.candidates == 4


def test_company_status_filter_only_restricts_companies(seeded: Session) -> None:
    filters = replace(PERIOD, company_status=CompanyStatus.APPROVED)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.totals.companies == 1
    assert indicators.totals.jobs == 2


def test_job_status_filter_only_restricts_jobs(seeded: Session) -> None:
    filters = replace(PERIOD, job_status=JobStatus.PUBLISHED)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.totals.jobs == 1
    assert indicators.totals.applications == 3


def test_application_status_filter_only_restricts_applications(
    seeded: Session,
) -> None:
    filters = replace(PERIOD, application_status=ApplicationStatus.HIRED)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.totals.applications == 1
    assert indicators.totals.matches == 2


def test_application_status_filter_does_not_change_placement(seeded: Session) -> None:
    filters = replace(PERIOD, application_status=ApplicationStatus.APPLIED)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.segments.candidates_without_placement == 1


def test_availability_filter_restricts_candidates_and_their_segments(
    seeded: Session,
) -> None:
    filters = replace(PERIOD, candidate_availability=AvailabilityStatus.UNAVAILABLE)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.totals.candidates == 1
    assert indicators.segments.candidates_without_placement == 0
    assert indicators.segments.incomplete_resumes == 1


def test_response_echoes_the_applied_filters(seeded: Session) -> None:
    filters = replace(PERIOD, job_status=JobStatus.PAUSED)

    indicators = get_platform_indicators(seeded, filters)

    assert indicators.filters.start_date == date(2001, 1, 1)
    assert indicators.filters.job_status == JobStatus.PAUSED
    assert indicators.filters.company_status is None


def test_endpoint_serializes_the_indicators(
    application: FastAPI, client: TestClient, seeded: Session
) -> None:
    application.dependency_overrides[require_administrator] = lambda: None
    application.dependency_overrides[get_session] = lambda: seeded

    response = client.get(
        INDICATORS_PATH,
        params={"start_date": "2001-01-01", "end_date": "2001-01-31"},
    )

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["totals"] == {
        "candidates": 3,
        "companies": 2,
        "jobs": 2,
        "applications": 3,
        "matches": 2,
    }
    assert body["segments"] == {
        "candidates_without_placement": 1,
        "candidates_with_unknown_employment": 1,
        "incomplete_resumes": 3,
    }
