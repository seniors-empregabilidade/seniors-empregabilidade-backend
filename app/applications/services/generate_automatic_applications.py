import logging
from collections import defaultdict
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import ColumnElement, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.applications.domain.policies.automatic_application_policy import (
    qualifies_for_automatic_application,
)
from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Job,
    JobSkill,
    Resume,
    ResumeSkill,
)
from app.db.models.enums import (
    AccountStatus,
    ApplicationStatus,
    ApplicationType,
    AvailabilityStatus,
)
from app.jobs.domain.policies.job_compatibility_policy import JobCompatibilityPolicy
from app.jobs.services import is_open_at, publishing_company_is_not_blocked

_logger = logging.getLogger("app.applications")


def generate_automatic_applications_for_job(
    session: Session,
    *,
    job_id: UUID,
    threshold_percent: int,
    now: datetime | None = None,
) -> int:
    """Apply, on their behalf, every eligible professional compatible with a job.

    Runs when a job is published, so every professional already registered is
    evaluated. Returns how many applications were created.
    """
    reference_now = now or datetime.now(UTC)
    is_open = session.scalar(
        select(Job.id)
        .join(AppUser, AppUser.id == Job.company_id)
        .where(
            Job.id == job_id,
            is_open_at(reference_now),
            publishing_company_is_not_blocked(),
        )
    )
    if is_open is None:
        return 0
    created = _apply_to_job(
        session,
        job_id=job_id,
        threshold_percent=threshold_percent,
    )
    _log_round("job", jobs=1, applications=created)
    return created


def generate_automatic_applications_for_open_jobs(
    session: Session,
    *,
    threshold_percent: int,
    now: datetime | None = None,
) -> int:
    """Evaluate every open job for every eligible professional without an application.

    Runs daily. Earlier accounts are evaluated again on purpose: a professional who
    turns the preference on, completes their skills or becomes available after a
    job was published must be applied on the next cycle (US-20-T05). The unique
    `(candidate_id, job_id)` constraint keeps the extra evaluations harmless, and a
    professional who withdrew keeps their row, so they are never applied again.
    Returns how many applications were created.
    """
    reference_now = now or datetime.now(UTC)
    open_jobs = session.execute(
        select(Job.id, Job.created_at)
        .join(AppUser, AppUser.id == Job.company_id)
        .where(is_open_at(reference_now), publishing_company_is_not_blocked())
        .order_by(Job.created_at, Job.id)
    ).all()
    created = 0
    for job in open_jobs:
        created += _apply_to_job(
            session,
            job_id=job.id,
            threshold_percent=threshold_percent,
        )
    _log_round("daily", jobs=len(open_jobs), applications=created)
    return created


def _apply_to_job(
    session: Session,
    *,
    job_id: UUID,
    threshold_percent: int,
) -> int:
    required_skill_ids = frozenset(
        session.scalars(select(JobSkill.skill_id).where(JobSkill.job_id == job_id))
    )
    if not required_skill_ids:
        return 0

    skill_ids_by_candidate = _shared_skill_ids_by_candidate(
        session,
        job_id=job_id,
        required_skill_ids=required_skill_ids,
    )
    scores = JobCompatibilityPolicy(required_skill_ids).rank(skill_ids_by_candidate)
    rows = [
        {
            "candidate_id": score.candidate_id,
            "job_id": job_id,
            "type": ApplicationType.AUTOMATIC,
            "status": ApplicationStatus.UNDER_REVIEW,
            "matched_requirements": score.matched_count,
            "total_requirements": score.required_count,
        }
        for score in scores
        if qualifies_for_automatic_application(score, threshold_percent)
    ]
    if not rows:
        return 0

    try:
        # The unique (candidate_id, job_id) constraint is what prevents a duplicate
        # under concurrency: the job-creation trigger and the daily one may overlap,
        # and a professional who applied meanwhile is simply skipped.
        inserted = session.scalars(
            insert(Application)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["candidate_id", "job_id"])
            .returning(Application.id)
        ).all()
        session.commit()
    except Exception:
        session.rollback()
        raise
    return len(inserted)


def _shared_skill_ids_by_candidate(
    session: Session,
    *,
    job_id: UUID,
    required_skill_ids: frozenset[UUID],
) -> dict[UUID, set[UUID]]:
    """Required skills held by each eligible professional who has not applied.

    Eligible means an active account that is available and keeps the automatic
    application preference on. A professional sharing no required skill cannot
    reach a threshold above zero, so they are left out.
    """
    has_applied = exists().where(
        Application.job_id == job_id, Application.candidate_id == Candidate.id
    )
    conditions: list[ColumnElement[bool]] = [
        ResumeSkill.skill_id.in_(required_skill_ids),
        AppUser.account_status == AccountStatus.ACTIVE,
        Candidate.availability == AvailabilityStatus.AVAILABLE,
        Candidate.accepts_automatic_application.is_(True),
        ~has_applied,
    ]
    rows = session.execute(
        select(Candidate.id, ResumeSkill.skill_id)
        .join(AppUser, AppUser.id == Candidate.id)
        .join(Resume, Resume.candidate_id == Candidate.id)
        .join(ResumeSkill, ResumeSkill.resume_id == Resume.id)
        .where(*conditions)
        .order_by(Candidate.id)
    ).all()
    skill_ids_by_candidate: dict[UUID, set[UUID]] = defaultdict(set)
    for candidate_id, skill_id in rows:
        skill_ids_by_candidate[candidate_id].add(skill_id)
    return skill_ids_by_candidate


def _log_round(trigger: str, *, jobs: int, applications: int) -> None:
    _logger.info(
        "automatic_applications_generated",
        extra={
            "event": "automatic_applications_generated",
            "trigger": trigger,
            "job_count": jobs,
            "application_count": applications,
        },
    )
