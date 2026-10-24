from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.account_management.exceptions import AccountNotFoundError
from app.account_management.schemas.account_detail_response import (
    AccountDetailResponse,
    AccountEducationResponse,
    AccountExperienceResponse,
    AccountSkillResponse,
)
from app.account_management.services.list_accounts import MANAGED_USER_TYPES
from app.db.models import (
    Address,
    Application,
    AppUser,
    Candidate,
    Company,
    Education,
    Experience,
    Job,
    Resume,
    ResumeSkill,
    Skill,
)
from app.db.models.enums import JobStatus, UserType


def get_account(session: Session, account_id: UUID) -> AccountDetailResponse:
    row = session.execute(
        select(
            AppUser.id,
            AppUser.user_type,
            AppUser.email,
            AppUser.account_status,
            AppUser.created_at,
            Candidate.full_name,
            Company.trade_name,
            Company.legal_name,
            Company.cnpj,
            Company.corporate_email,
            Company.industry,
            Company.company_size,
            Company.status,
            Address.city,
            Address.state,
            Resume.id.label("resume_id"),
            Resume.summary,
            Resume.completion_percentage,
        )
        .select_from(AppUser)
        .outerjoin(Candidate, Candidate.id == AppUser.id)
        .outerjoin(Company, Company.id == AppUser.id)
        .outerjoin(Address, Address.id == Company.address_id)
        .outerjoin(Resume, Resume.candidate_id == Candidate.id)
        .where(
            AppUser.id == account_id,
            AppUser.user_type.in_(MANAGED_USER_TYPES),
        )
    ).one_or_none()
    if row is None:
        raise AccountNotFoundError

    is_candidate = row.user_type == UserType.CANDIDATE
    experiences: list[AccountExperienceResponse] = []
    education: list[AccountEducationResponse] = []
    skills: list[AccountSkillResponse] = []
    if is_candidate and row.resume_id is not None:
        experiences, education, skills = _resume_sections(session, row.resume_id)

    return AccountDetailResponse(
        id=row.id,
        user_type=row.user_type,
        email=row.email,
        display_name=row.full_name or row.trade_name or row.legal_name,
        account_status=row.account_status,
        company_status=row.status,
        completion_percentage=(
            (row.completion_percentage or 0) if is_candidate else None
        ),
        created_at=row.created_at,
        application_count=_application_count(session, row.id) if is_candidate else None,
        summary=row.summary if is_candidate else None,
        experiences=experiences,
        education=education,
        skills=skills,
        legal_name=None if is_candidate else row.legal_name,
        trade_name=None if is_candidate else row.trade_name,
        cnpj=None if is_candidate else row.cnpj,
        corporate_email=None if is_candidate else row.corporate_email,
        city=None if is_candidate else row.city,
        state=None if is_candidate else row.state,
        industry=None if is_candidate else row.industry,
        company_size=None if is_candidate else row.company_size,
        published_job_count=(
            None if is_candidate else _published_job_count(session, row.id)
        ),
    )


def _published_job_count(session: Session, company_id: UUID) -> int:
    return (
        session.scalar(
            select(func.count(Job.id)).where(
                Job.company_id == company_id,
                Job.status == JobStatus.PUBLISHED,
            )
        )
        or 0
    )


def _application_count(session: Session, candidate_id: UUID) -> int:
    return (
        session.scalar(
            select(func.count(Application.id)).where(
                Application.candidate_id == candidate_id
            )
        )
        or 0
    )


def _resume_sections(
    session: Session, resume_id: UUID
) -> tuple[
    list[AccountExperienceResponse],
    list[AccountEducationResponse],
    list[AccountSkillResponse],
]:
    experiences = [
        AccountExperienceResponse(
            id=item.id,
            role=item.role,
            company_name=item.company_name,
            start_date=item.start_date,
            end_date=item.end_date,
        )
        for item in session.scalars(
            select(Experience)
            .where(Experience.resume_id == resume_id)
            .order_by(Experience.start_date.desc(), Experience.id)
        )
    ]
    education = [
        AccountEducationResponse(
            id=item.id,
            institution=item.institution,
            degree=item.degree,
            field=item.field,
            start_date=item.start_date,
            end_date=item.end_date,
        )
        for item in session.scalars(
            select(Education)
            .where(Education.resume_id == resume_id)
            .order_by(Education.start_date.desc().nulls_last(), Education.id)
        )
    ]
    skills = [
        AccountSkillResponse(id=item.id, name=item.name)
        for item in session.scalars(
            select(Skill)
            .join(ResumeSkill, ResumeSkill.skill_id == Skill.id)
            .where(ResumeSkill.resume_id == resume_id)
            .order_by(Skill.name, Skill.id)
        )
    ]
    return experiences, education, skills
