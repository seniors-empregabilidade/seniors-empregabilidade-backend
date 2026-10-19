from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import Row, exists, select
from sqlalchemy.orm import Session

from app.db.models import (
    Application,
    AppUser,
    Candidate,
    Job,
    JobSkill,
    Resume,
    ResumeSkill,
)
from app.db.models.enums import AccountStatus, ApplicationStatus, AvailabilityStatus
from app.jobs.domain.candidate_origin import CandidateOrigin
from app.jobs.domain.policies.automatic_match_policy import is_automatic_match
from app.jobs.domain.policies.job_compatibility_policy import JobCompatibilityPolicy
from app.jobs.domain.value_objects.compatibility_score import CompatibilityScore
from app.jobs.exceptions import JobNotFoundError


@dataclass(frozen=True, slots=True)
class ApplicantProfile:
    """Candidate data safe for the company to evaluate a profile.

    The same fields are exposed for applicants and automatic matches; contact and
    identification data (email, phone, CPF, birth date) never are.
    """

    candidate_id: UUID
    full_name: str
    city: str | None
    state: str | None


@dataclass(frozen=True, slots=True)
class JobApplicant:
    """One professional in a job's list: an applicant or an automatic match.

    An automatic match has no application, so ``application_id``, ``status`` and
    ``match_score`` are ``None``. The compatibility fields come from the same
    engine for both origins.
    """

    origin: CandidateOrigin
    application_id: UUID | None
    status: ApplicationStatus | None
    match_score: int | None
    compatibility_percentage: Decimal | None
    is_highlighted: bool
    matched_skill_count: int
    required_skill_count: int
    profile: ApplicantProfile

    @property
    def is_application(self) -> bool:
        return self.origin is CandidateOrigin.APPLICATION

    @property
    def is_full_match(self) -> bool:
        return 0 < self.required_skill_count == self.matched_skill_count


@dataclass(frozen=True, slots=True)
class JobApplicantsSummary:
    """Aggregate header for the list.

    ``total_applicant_count`` and ``full_match_count`` count applications only;
    ``automatic_match_count`` counts the compatible profiles that did not apply.
    """

    job_id: UUID
    total_applicant_count: int
    full_match_count: int
    automatic_match_count: int
    applicants: list[JobApplicant] = field(default_factory=list)


def list_job_applicants(
    session: Session,
    *,
    job_id: UUID,
    company_id: UUID,
) -> JobApplicantsSummary:
    """List a company job's applicants and automatic matches, ranked together.

    The company can only access its own jobs: a job belonging to a different
    company is indistinguishable from a non-existent one and raises
    ``JobNotFoundError`` (404). No personal data beyond what is needed for the
    evaluation (name, city, state) is exposed, whatever the origin.

    Every applicant is listed with ``origin`` ``application``. A professional who
    did not apply is listed with ``origin`` ``automatic_match`` when
    ``is_automatic_match`` accepts their score (US-20); only active accounts that
    declare themselves available are considered.

    Both origins are ranked by ``JobCompatibilityPolicy``: compatibility percentage
    descending, the same percentage for the same skills whatever the origin.
    Equal percentages list applicants first, in application order (oldest first),
    then automatic matches by ``candidate_id``.
    A job without required skills cannot be scored, so it has no automatic
    matches and its applicants keep the application order with a null percentage.
    """
    job = session.scalar(
        select(Job).where(Job.id == job_id, Job.company_id == company_id)
    )
    if job is None:
        raise JobNotFoundError

    required_skill_ids: frozenset[UUID] = frozenset(
        session.scalars(select(JobSkill.skill_id).where(JobSkill.job_id == job_id))
    )

    applicant_rows = session.execute(
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
        listed = _ranked_list(
            session,
            job_id=job_id,
            applicant_rows=applicant_rows,
            required_skill_ids=required_skill_ids,
        )
    else:
        listed = [_unscored_applicant(row) for row in applicant_rows]

    applicants = [entry for entry in listed if entry.is_application]
    return JobApplicantsSummary(
        job_id=job_id,
        total_applicant_count=len(applicants),
        full_match_count=sum(applicant.is_full_match for applicant in applicants),
        automatic_match_count=len(listed) - len(applicants),
        applicants=listed,
    )


def _ranked_list(
    session: Session,
    *,
    job_id: UUID,
    applicant_rows: Sequence[Row[Any]],
    required_skill_ids: frozenset[UUID],
) -> list[JobApplicant]:
    """Score applicants and candidate matches with one engine and rank them.

    The policy keeps the given order for equal percentages, so applicants (in
    application order) are given before automatic matches (by ``candidate_id``).
    """
    applicant_rows_by_candidate = {row.candidate_id: row for row in applicant_rows}
    match_candidate_ids = _automatic_match_candidate_ids(
        session, job_id=job_id, required_skill_ids=required_skill_ids
    )
    resume_skills_by_candidate = _resume_skills_by_candidate(
        session, candidate_ids=[*applicant_rows_by_candidate, *match_candidate_ids]
    )
    ranking = JobCompatibilityPolicy(required_skill_ids).rank(
        {
            candidate_id: resume_skills_by_candidate[candidate_id]
            for candidate_id in (*applicant_rows_by_candidate, *match_candidate_ids)
        }
    )
    listed = [
        score
        for score in ranking
        if score.candidate_id in applicant_rows_by_candidate
        or is_automatic_match(score)
    ]
    match_rows_by_candidate = _profile_rows_by_candidate(
        session,
        candidate_ids=[
            score.candidate_id
            for score in listed
            if score.candidate_id not in applicant_rows_by_candidate
        ],
    )
    return [
        _scored_applicant(applicant_rows_by_candidate[score.candidate_id], score)
        if score.candidate_id in applicant_rows_by_candidate
        else _automatic_match(match_rows_by_candidate[score.candidate_id], score)
        for score in listed
    ]


def _automatic_match_candidate_ids(
    session: Session, *, job_id: UUID, required_skill_ids: frozenset[UUID]
) -> list[UUID]:
    """Candidates who may be automatic matches, ordered by ``candidate_id``.

    Selects active, available candidates who have not applied to the job and share
    at least one required skill: a necessary condition for any percentage above
    zero. Whether one is compatible enough is decided by ``is_automatic_match``.
    """
    has_applied = exists().where(
        Application.job_id == job_id, Application.candidate_id == Candidate.id
    )
    return list(
        session.scalars(
            select(Candidate.id)
            .join(AppUser, AppUser.id == Candidate.id)
            .join(Resume, Resume.candidate_id == Candidate.id)
            .join(ResumeSkill, ResumeSkill.resume_id == Resume.id)
            .where(
                ResumeSkill.skill_id.in_(required_skill_ids),
                AppUser.account_status == AccountStatus.ACTIVE,
                Candidate.availability == AvailabilityStatus.AVAILABLE,
                ~has_applied,
            )
            .distinct()
            .order_by(Candidate.id)
        )
    )


def _profile_rows_by_candidate(
    session: Session, *, candidate_ids: list[UUID]
) -> dict[UUID, Row[Any]]:
    if not candidate_ids:
        return {}
    rows = session.execute(
        select(
            Candidate.id.label("candidate_id"),
            Candidate.full_name,
            Candidate.city,
            Candidate.state,
        ).where(Candidate.id.in_(candidate_ids))
    ).all()
    return {row.candidate_id: row for row in rows}


def _scored_applicant(row: Row[Any], score: CompatibilityScore) -> JobApplicant:
    return JobApplicant(
        origin=CandidateOrigin.APPLICATION,
        application_id=row.application_id,
        status=row.status,
        match_score=row.match_score,
        compatibility_percentage=score.percentage,
        is_highlighted=score.is_highlighted,
        matched_skill_count=score.matched_count,
        required_skill_count=score.required_count,
        profile=_profile(row),
    )


def _automatic_match(row: Row[Any], score: CompatibilityScore) -> JobApplicant:
    return JobApplicant(
        origin=CandidateOrigin.AUTOMATIC_MATCH,
        application_id=None,
        status=None,
        match_score=None,
        compatibility_percentage=score.percentage,
        is_highlighted=score.is_highlighted,
        matched_skill_count=score.matched_count,
        required_skill_count=score.required_count,
        profile=_profile(row),
    )


def _unscored_applicant(row: Row[Any]) -> JobApplicant:
    return JobApplicant(
        origin=CandidateOrigin.APPLICATION,
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
