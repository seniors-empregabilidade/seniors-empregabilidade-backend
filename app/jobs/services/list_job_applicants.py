from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, select
from sqlalchemy.orm import Session

from app.db.models import Application, Candidate, Job, JobSkill, Resume, ResumeSkill
from app.db.models.enums import ApplicationStatus
from app.jobs.domain.policies.job_compatibility_policy import JobCompatibilityPolicy
from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore
from app.jobs.exceptions import JobNotFoundError


@dataclass(frozen=True, slots=True)
class ApplicantProfile:
    """Candidate data safe for the company to evaluate an application."""

    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None


@dataclass(frozen=True, slots=True)
class JobApplicant:
    """One candidate row returned in the job-applicants list."""

    application_id: UUID
    status: ApplicationStatus
    match_score: int | None
    compatibility_percentage: Decimal | None
    is_highlighted: bool
    matched_skill_count: int
    required_skill_count: int
    profile: ApplicantProfile

    @property
    def is_full_match(self) -> bool:
        return 0 < self.required_skill_count == self.matched_skill_count


@dataclass(frozen=True, slots=True)
class JobApplicantsSummary:
    """Aggregate header for the applicants list."""

    job_id: UUID
    total_applicant_count: int
    full_match_count: int
    applicants: list[JobApplicant] = field(default_factory=list)


def list_job_applicants(
    session: Session,
    *,
    job_id: UUID,
    company_id: UUID,
) -> JobApplicantsSummary:
    """List every candidate who applied to a company's job, ranked by compatibility.

    The company can only access applicants for its own jobs: a job belonging
    to a different company is indistinguishable from a non-existent one and
    raises ``JobNotFoundError`` (404). No personal data beyond what is needed
    for the evaluation (name, city, state) is exposed.

    Applicants are ranked by ``JobCompatibilityPolicy``: compatibility
    percentage descending; equal percentages keep the application order (oldest
    first). Applicants at 50% or more are highlighted and come first; the others
    stay in the list after them.
    A job without required skills cannot be scored, so its applicants keep the
    application order (oldest first) with a null percentage.
    """
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.company_id == company_id)
    )
    if job is None:
        raise JobNotFoundError

    required_skill_ids: frozenset[UUID] = frozenset(
        session.scalars(select(JobSkill.skill_id).where(JobSkill.job_id == job_id))
    )

    rows = session.execute(
        select(
            Application.id.label("application_id"),
            Application.candidate_id,
            Application.status,
            Application.match_score,
            Candidate.full_name,
            Candidate.city,
            Candidate.state,
        )
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id)
        .order_by(Application.created_at, Application.id)
    ).all()

    if required_skill_ids:
        applicants = _ranked_applicants(
            session, rows=rows, required_skill_ids=required_skill_ids
        )
    else:
        applicants = [_unscored_applicant(row) for row in rows]

    return JobApplicantsSummary(
        job_id=job_id,
        total_applicant_count=len(applicants),
        full_match_count=sum(applicant.is_full_match for applicant in applicants),
        applicants=applicants,
    )


def _ranked_applicants(
    session: Session, *, rows: Sequence[Row[Any]], required_skill_ids: frozenset[UUID]
) -> list[JobApplicant]:
    """Rank applicants with the compatibility engine.

    ``rows`` arrive in application order and the policy keeps that order for equal
    percentages, so the oldest application wins a tie.
    """
    rows_by_candidate = {row.candidate_id: row for row in rows}
    resume_skills_by_candidate = _resume_skills_by_candidate(
        session, candidate_ids=list(rows_by_candidate)
    )
    ranking = JobCompatibilityPolicy(required_skill_ids).rank(
        {
            candidate_id: resume_skills_by_candidate[candidate_id]
            for candidate_id in rows_by_candidate
        }
    )
    return [
        _scored_applicant(rows_by_candidate[score.candidate_id], score)
        for score in ranking
    ]


def _scored_applicant(row: Row[Any], score: CompatibilityScore) -> JobApplicant:
    return JobApplicant(
        application_id=row.application_id,
        status=row.status,
        match_score=row.match_score,
        compatibility_percentage=score.percentage,
        is_highlighted=score.is_highlighted,
        matched_skill_count=score.matched_count,
        required_skill_count=score.required_count,
        profile=_profile(row),
    )


def _unscored_applicant(row: Row[Any]) -> JobApplicant:
    return JobApplicant(
        application_id=row.application_id,
        status=row.status,
        match_score=row.match_score,
        compatibility_percentage=None,
        is_highlighted=False,
        matched_skill_count=0,
        required_skill_count=0,
        profile=_profile(row),
    )


def _profile(row: Row[Any]) -> ApplicantProfile:
    return ApplicantProfile(
        candidate_id=row.candidate_id,
        full_name=row.full_name,
        city=row.city,
        state=row.state,
    )


def _resume_skills_by_candidate(
    session: Session, *, candidate_ids: list[UUID]
) -> defaultdict[UUID, frozenset[UUID]]:
    """Map candidate_id → frozenset of their resume skill IDs."""
    result: defaultdict[UUID, frozenset[UUID]] = defaultdict(frozenset)
    if not candidate_ids:
        return result

    rows = session.execute(
        select(Resume.candidate_id, ResumeSkill.skill_id)
        .join(ResumeSkill, ResumeSkill.resume_id == Resume.id)
        .where(Resume.candidate_id.in_(candidate_ids))
    ).all()

    skills_by_candidate: defaultdict[UUID, set[UUID]] = defaultdict(set)
    for candidate_id, skill_id in rows:
        skills_by_candidate[candidate_id].add(skill_id)

    for candidate_id, skills in skills_by_candidate.items():
        result[candidate_id] = frozenset(skills)

    return result
