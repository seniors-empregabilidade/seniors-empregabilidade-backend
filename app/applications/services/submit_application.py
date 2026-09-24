from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from psycopg.errors import UniqueViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.applications.domain.policies.local_date import to_local_date
from app.applications.domain.policies.requirement_match import match_requirements
from app.applications.exceptions import (
    ApplicationAlreadyExistsError,
    JobNotFoundError,
    JobNotOpenError,
)
from app.db.models import Application, Job, JobSkill, Resume, ResumeSkill
from app.db.models.enums import ApplicationStatus, JobStatus

_UNIQUE_CANDIDATE_JOB_CONSTRAINT = "uq_application_candidate_id_job_id"


@dataclass(frozen=True, slots=True)
class SubmittedApplication:
    id: UUID
    job_id: UUID
    status: ApplicationStatus
    submitted_at: datetime
    matched_requirements: int
    total_requirements: int


def submit_application(
    session: Session,
    *,
    job_id: UUID,
    candidate_id: UUID,
    now: datetime | None = None,
) -> SubmittedApplication:
    """Register the authenticated candidate's application to an open job.

    An open job is published and still within its closing date, the same
    criterion `find_similar_jobs` uses (evaluated as a calendar date in
    `LOCAL_TIMEZONE`). Compatibility is computed once, here, from the job's
    required skills (`job_skill`) and the candidate's resume skills
    (`resume_skill`); it is never recalculated afterward, even if the job's
    requirements or the candidate's resume change later (see
    docs/APPLICATIONS.md).

    The `(candidate_id, job_id)` unique constraint (already part of the
    initial schema) is what actually prevents a duplicate application under
    concurrency: two simultaneous requests both pass the checks below, but
    only one `INSERT` wins; the loser's `IntegrityError` is translated into
    `ApplicationAlreadyExistsError` (`409`) instead of creating a second row.
    """
    reference_now = now or datetime.now(UTC)
    today = to_local_date(reference_now)

    job = session.get(Job, job_id)
    if job is None:
        raise JobNotFoundError
    if job.status != JobStatus.PUBLISHED or job.closing_date < today:
        raise JobNotOpenError

    required_skill_ids = session.scalars(
        select(JobSkill.skill_id).where(JobSkill.job_id == job_id)
    ).all()
    candidate_skill_ids = session.scalars(
        select(ResumeSkill.skill_id)
        .join(Resume, Resume.id == ResumeSkill.resume_id)
        .where(Resume.candidate_id == candidate_id)
    ).all()
    match = match_requirements(
        required_skill_ids=required_skill_ids,
        candidate_skill_ids=candidate_skill_ids,
    )

    application = Application(
        candidate_id=candidate_id,
        job_id=job_id,
        status=ApplicationStatus.UNDER_REVIEW,
        matched_requirements=match.matched,
        total_requirements=match.total,
    )
    try:
        session.add(application)
        session.flush()
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        original = exc.orig
        if (
            isinstance(original, UniqueViolation)
            and original.diag.constraint_name == _UNIQUE_CANDIDATE_JOB_CONSTRAINT
        ):
            raise ApplicationAlreadyExistsError from exc
        raise
    except Exception:
        session.rollback()
        raise

    return SubmittedApplication(
        id=application.id,
        job_id=application.job_id,
        status=application.status,
        submitted_at=application.created_at,
        matched_requirements=match.matched,
        total_requirements=match.total,
    )
