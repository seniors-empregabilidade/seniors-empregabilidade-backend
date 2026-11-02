import os
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import delete, select, update

from app.applications.services.generate_automatic_applications import (
    generate_automatic_applications_for_job,
    generate_automatic_applications_for_open_jobs,
)
from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Company,
    Job,
    JobSkill,
    Resume,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    ApplicationType,
    AvailabilityStatus,
    JobStatus,
    UserType,
)
from app.db.session import get_session_factory

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

THRESHOLD = 70


@dataclass(frozen=True, slots=True)
class AutomaticScenario:
    now: datetime
    job_id: UUID
    """Published, requires four skills, created ten days ago."""
    draft_job_id: UUID
    """Same requirements, but not published."""
    high_id: UUID
    """Registered before the job; holds 3 of 4 skills (75%)."""
    low_id: UUID
    """Registered before the job; holds 2 of 4 skills (50%)."""
    opted_out_id: UUID
    """Registered before the job; holds all skills but turned the preference off."""
    unavailable_id: UUID
    """Registered before the job; holds all skills but is unavailable."""
    blocked_id: UUID
    """Registered before the job; holds all skills but the account is blocked."""
    applied_id: UUID
    """Registered before the job; holds all skills and already applied."""
    late_high_id: UUID
    """Registered after the job; holds 3 of 4 skills (75%)."""
    late_low_id: UUID
    """Registered after the job; holds 2 of 4 skills (50%)."""
    existing_application_id: UUID


@pytest.fixture
def scenario() -> Iterator[AutomaticScenario]:
    now = datetime.now(UTC)
    factory = get_session_factory()
    user_ids: list[UUID] = []
    skill_ids: list[UUID] = []

    with factory.begin() as session:
        company_user = AppUser(
            email="automatic-company@synthetic.example.invalid",
            identity_subject=None,
            user_type=UserType.COMPANY,
            created_at=now - timedelta(days=60),
        )
        session.add(company_user)
        session.flush()
        user_ids.append(company_user.id)
        session.add(
            Company(
                id=company_user.id,
                cnpj="90000000000100",
                legal_name="Automatic Synthetic Services Ltd.",
                trade_name="Automatic Synthetic Services",
                corporate_email=company_user.email,
                status="approved",
            )
        )

        skills = [
            Skill(
                name=f"Automatic Skill {index}",
                normalized_name=f"automatic skill {index}",
                type="hard",
            )
            for index in range(4)
        ]
        session.add_all(skills)
        session.flush()
        skill_ids.extend(skill.id for skill in skills)

        def make_job(title: str, status: JobStatus) -> Job:
            job = Job(
                company_id=company_user.id,
                title=title,
                description="Synthetic job for automatic application tests.",
                work_mode="remote",
                status=status,
                closing_date=date(2099, 12, 31),
                created_at=now - timedelta(days=10),
            )
            session.add(job)
            session.flush()
            session.add_all(
                JobSkill(job_id=job.id, skill_id=skill.id) for skill in skills
            )
            return job

        job = make_job("Automatic Open Role", JobStatus.PUBLISHED)
        draft_job = make_job("Automatic Draft Role", JobStatus.DRAFT)

        def make_candidate(
            name: str,
            *,
            skill_count: int,
            registered_at: datetime,
            availability: AvailabilityStatus = AvailabilityStatus.AVAILABLE,
            accepts: bool = True,
            account_status: AccountStatus = AccountStatus.ACTIVE,
        ) -> UUID:
            user = AppUser(
                email=f"automatic-{name}@synthetic.example.invalid",
                identity_subject=None,
                user_type=UserType.CANDIDATE,
                account_status=account_status,
                created_at=registered_at,
            )
            session.add(user)
            session.flush()
            user_ids.append(user.id)
            session.add(
                Candidate(
                    id=user.id,
                    full_name=f"Automatic {name}",
                    cpf=f"{len(user_ids):011d}",
                    birth_date=date(1970, 1, 1),
                    phone="+5551999990000",
                    availability=availability,
                    accepts_automatic_application=accepts,
                )
            )
            resume = Resume(candidate_id=user.id)
            session.add(resume)
            session.flush()
            session.add_all(
                ResumeSkill(resume_id=resume.id, skill_id=skill.id)
                for skill in skills[:skill_count]
            )
            return user.id

        before = now - timedelta(days=20)
        after = now - timedelta(days=1)
        high_id = make_candidate("high", skill_count=3, registered_at=before)
        low_id = make_candidate("low", skill_count=2, registered_at=before)
        opted_out_id = make_candidate(
            "opted-out", skill_count=4, registered_at=before, accepts=False
        )
        unavailable_id = make_candidate(
            "unavailable",
            skill_count=4,
            registered_at=before,
            availability=AvailabilityStatus.UNAVAILABLE,
        )
        blocked_id = make_candidate(
            "blocked",
            skill_count=4,
            registered_at=before,
            account_status=AccountStatus.BLOCKED,
        )
        applied_id = make_candidate("applied", skill_count=4, registered_at=before)
        late_high_id = make_candidate("late-high", skill_count=3, registered_at=after)
        late_low_id = make_candidate("late-low", skill_count=2, registered_at=after)

        existing = Application(
            candidate_id=applied_id,
            job_id=job.id,
            status=ApplicationStatus.APPLIED,
        )
        session.add(existing)
        session.flush()

        result = AutomaticScenario(
            now=now,
            job_id=job.id,
            draft_job_id=draft_job.id,
            high_id=high_id,
            low_id=low_id,
            opted_out_id=opted_out_id,
            unavailable_id=unavailable_id,
            blocked_id=blocked_id,
            applied_id=applied_id,
            late_high_id=late_high_id,
            late_low_id=late_low_id,
            existing_application_id=existing.id,
        )

    yield result

    with factory.begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))
        session.execute(delete(Skill).where(Skill.id.in_(skill_ids)))


def _applied_candidate_ids(job_id: UUID) -> set[UUID]:
    with get_session_factory()() as session:
        return set(
            session.scalars(
                select(Application.candidate_id).where(Application.job_id == job_id)
            )
        )


def test_new_job_applies_only_for_eligible_compatible_professionals(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        created = generate_automatic_applications_for_job(
            session,
            job_id=scenario.job_id,
            threshold_percent=THRESHOLD,
            now=scenario.now,
        )

    assert created == 2
    assert _applied_candidate_ids(scenario.job_id) == {
        scenario.high_id,
        scenario.late_high_id,
        scenario.applied_id,
    }


def test_generated_application_is_marked_automatic_with_its_requirement_counts(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        generate_automatic_applications_for_job(
            session,
            job_id=scenario.job_id,
            threshold_percent=THRESHOLD,
            now=scenario.now,
        )

    with get_session_factory()() as session:
        stored = session.scalars(
            select(Application).where(
                Application.job_id == scenario.job_id,
                Application.candidate_id == scenario.high_id,
            )
        ).one()
    assert stored.type == ApplicationType.AUTOMATIC
    assert stored.status == ApplicationStatus.UNDER_REVIEW
    assert stored.matched_requirements == 3
    assert stored.total_requirements == 4


def test_lower_threshold_includes_less_compatible_professionals(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        generate_automatic_applications_for_job(
            session, job_id=scenario.job_id, threshold_percent=50, now=scenario.now
        )

    assert {scenario.low_id, scenario.late_low_id} <= _applied_candidate_ids(
        scenario.job_id
    )


def test_job_that_is_not_published_generates_nothing(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        created = generate_automatic_applications_for_job(
            session,
            job_id=scenario.draft_job_id,
            threshold_percent=THRESHOLD,
            now=scenario.now,
        )

    assert created == 0
    assert _applied_candidate_ids(scenario.draft_job_id) == set()


def test_running_again_never_duplicates_an_application(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        generate_automatic_applications_for_job(
            session,
            job_id=scenario.job_id,
            threshold_percent=THRESHOLD,
            now=scenario.now,
        )
        again = generate_automatic_applications_for_job(
            session,
            job_id=scenario.job_id,
            threshold_percent=THRESHOLD,
            now=scenario.now,
        )

    assert again == 0
    with get_session_factory()() as session:
        stored = session.scalars(
            select(Application).where(
                Application.job_id == scenario.job_id,
                Application.candidate_id == scenario.applied_id,
            )
        ).all()
    assert [row.id for row in stored] == [scenario.existing_application_id]
    assert stored[0].type == ApplicationType.ACTIVE


def test_daily_round_evaluates_every_eligible_professional(
    scenario: AutomaticScenario,
) -> None:
    with get_session_factory()() as session:
        generate_automatic_applications_for_open_jobs(
            session, threshold_percent=THRESHOLD, now=scenario.now
        )

    applied = _applied_candidate_ids(scenario.job_id)
    # Accounts older than the job count too: they may have become eligible
    # after it was published.
    assert {scenario.high_id, scenario.late_high_id} <= applied
    assert applied.isdisjoint(
        {
            scenario.low_id,
            scenario.late_low_id,
            scenario.opted_out_id,
            scenario.unavailable_id,
            scenario.blocked_id,
        }
    )
    assert _applied_candidate_ids(scenario.draft_job_id) == set()


def test_turning_the_preference_on_applies_on_the_next_daily_round(
    scenario: AutomaticScenario,
) -> None:
    # US-20-T05: the professional had the preference off when the job was
    # published and turns it on afterwards.
    with get_session_factory()() as session:
        generate_automatic_applications_for_job(
            session, job_id=scenario.job_id, threshold_percent=THRESHOLD
        )
    assert scenario.opted_out_id not in _applied_candidate_ids(scenario.job_id)

    with get_session_factory().begin() as session:
        session.execute(
            update(Candidate)
            .where(Candidate.id == scenario.opted_out_id)
            .values(accepts_automatic_application=True)
        )
    with get_session_factory()() as session:
        generate_automatic_applications_for_open_jobs(
            session, threshold_percent=THRESHOLD, now=scenario.now
        )

    assert scenario.opted_out_id in _applied_candidate_ids(scenario.job_id)
