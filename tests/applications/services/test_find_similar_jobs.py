import os
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.applications.services.find_similar_jobs import find_similar_jobs
from app.db.models import AppUser, Company, Job, JobSkill, Skill
from app.db.models.enums import (
    AccountStatus,
    CompanyStatus,
    JobStatus,
    SkillType,
    UserType,
)
from app.db.session import get_session_factory
from tests.applications.conftest import ApplicationsScenario

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]


def test_ranks_published_jobs_by_shared_skill_count(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_target_id,
            candidate_id=scenario.owner_id,
            now=scenario.now,
        )

    ids = [str(job.id) for job in suggestions]
    assert ids[:2] == [
        str(scenario.job_similar_strong_id),
        str(scenario.job_similar_weak_id),
    ]
    assert str(scenario.job_no_match_id) not in ids
    assert str(scenario.job_already_applied_id) not in ids
    assert str(scenario.job_draft_id) not in ids
    assert str(scenario.job_target_id) not in ids


def test_limit_caps_the_number_of_suggestions(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_target_id,
            candidate_id=scenario.owner_id,
            limit=1,
            now=scenario.now,
        )

    assert len(suggestions) == 1
    assert suggestions[0].id == scenario.job_similar_strong_id


def test_a_job_with_no_shared_skills_has_no_suggestions(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_no_match_id,
            candidate_id=scenario.owner_id,
            now=scenario.now,
        )

    assert suggestions == []


def test_a_job_past_its_closing_date_is_never_suggested(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_closing_pivot_id,
            candidate_id=scenario.owner_id,
            now=scenario.now,
        )

    ids = [job.id for job in suggestions]
    assert scenario.job_expired_id not in ids


def test_a_job_closing_today_is_still_suggested(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_closing_pivot_id,
            candidate_id=scenario.owner_id,
            now=scenario.now,
        )

    ids = [job.id for job in suggestions]
    assert scenario.job_closing_today_id in ids


def test_a_job_with_a_future_closing_date_is_suggested(
    scenario: ApplicationsScenario,
) -> None:
    with get_session_factory()() as session:
        suggestions = find_similar_jobs(
            session,
            job_id=scenario.job_target_id,
            candidate_id=scenario.owner_id,
            now=scenario.now,
        )

    # job_similar_strong_id and job_similar_weak_id both have a far-future
    # closing date (see conftest); either one demonstrates the case.
    ids = [job.id for job in suggestions]
    assert scenario.job_similar_strong_id in ids


def test_an_open_job_of_a_blocked_company_is_never_suggested(
    database_session: Session,
) -> None:
    marker = uuid4().hex[:10]

    def company(status: AccountStatus) -> AppUser:
        user = AppUser(
            email=f"similar-{marker}-{status.value}@company.example.invalid",
            identity_subject=None,
            user_type=UserType.COMPANY,
            account_status=status,
        )
        database_session.add(user)
        database_session.flush()
        database_session.add(
            Company(
                id=user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name=f"Similar {status.value} {marker}",
                corporate_email=user.email,
                status=CompanyStatus.APPROVED,
            )
        )
        return user

    active = company(AccountStatus.ACTIVE)
    blocked = company(AccountStatus.BLOCKED)
    skill = Skill(
        name=f"Similar {marker}",
        normalized_name=f"similar {marker}",
        type=SkillType.HARD,
    )
    database_session.add(skill)
    database_session.flush()

    def job(owner: AppUser) -> Job:
        created = Job(
            company_id=owner.id,
            title=f"Similar {marker} {owner.account_status.value}",
            description="Synthetic job for blocked-company suggestions.",
            work_mode="remote",
            status=JobStatus.PUBLISHED,
            closing_date=date(2099, 12, 31),
        )
        database_session.add(created)
        database_session.flush()
        database_session.add(JobSkill(job_id=created.id, skill_id=skill.id))
        return created

    source = job(active)
    job(blocked)

    suggestions = find_similar_jobs(
        database_session, job_id=source.id, candidate_id=uuid4()
    )

    assert suggestions == []
