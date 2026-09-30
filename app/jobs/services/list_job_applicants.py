from collections import defaultdict
from dataclasses import dataclass, field
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Application, Candidate, Job, JobSkill, Resume, ResumeSkill
from app.db.models.enums import ApplicationStatus
from app.jobs.domain.policies.skill_match import match_skills
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
    matched_skill_count: int
    required_skill_count: int
    profile: ApplicantProfile


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
    """List every candidate who applied to a company's job, with skill match.

    The company can only access applicants for its own jobs: a job belonging
    to a different company is indistinguishable from a non-existent one and
    raises ``JobNotFoundError`` (404). No personal data beyond what is needed
    for the evaluation (name, city, state) is exposed.

    Applicants are ordered by ``match_score`` descending (most compatible
    first) then by application creation date (oldest first) as a stable
    tiebreaker.
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
            Application.created_at.label("applied_at"),
            Candidate.full_name,
            Candidate.city,
            Candidate.state,
        )
        .join(Candidate, Candidate.id == Application.candidate_id)
        .where(Application.job_id == job_id)
        .order_by(
            Application.match_score.desc().nulls_last(),
            Application.created_at,
            Application.id,
        )
    ).all()

    if not rows:
        return JobApplicantsSummary(
            job_id=job_id,
            total_applicant_count=0,
            full_match_count=0,
            applicants=[],
        )

    candidate_ids = [row.candidate_id for row in rows]
    resume_skills_by_candidate = _resume_skills_by_candidate(
        session, candidate_ids=candidate_ids
    )

    applicants: list[JobApplicant] = []
    full_match_count = 0
    for row in rows:
        candidate_skill_ids = resume_skills_by_candidate[row.candidate_id]
        match = match_skills(
            candidate_skill_ids=candidate_skill_ids,
            required_skill_ids=required_skill_ids,
        )
        if match.matched_count == match.required_count and match.required_count > 0:
            full_match_count += 1
        applicants.append(
            JobApplicant(
                application_id=row.application_id,
                status=row.status,
                match_score=row.match_score,
                matched_skill_count=match.matched_count,
                required_skill_count=match.required_count,
                profile=ApplicantProfile(
                    candidate_id=row.candidate_id,
                    full_name=row.full_name,
                    city=row.city,
                    state=row.state,
                ),
            )
        )

    return JobApplicantsSummary(
        job_id=job_id,
        total_applicant_count=len(applicants),
        full_match_count=full_match_count,
        applicants=applicants,
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
