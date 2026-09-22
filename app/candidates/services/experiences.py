from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import (
    ExperienceNotFoundError,
    InvalidExperiencePeriodError,
)
from app.candidates.schemas.experience import (
    ExperienceCreateRequest,
    ExperienceUpdateRequest,
)
from app.candidates.services.records import ExperienceRecord, experience_record
from app.candidates.services.resumes import get_or_create_resume
from app.db.models.experience import Experience
from app.db.models.resume import Resume


def add_experience(
    user_id: UUID, request: ExperienceCreateRequest, *, session: Session
) -> ExperienceRecord:
    try:
        _ensure_valid_period(request.start_date, request.end_date)
        resume = get_or_create_resume(user_id, session)
        experience = Experience(
            resume_id=resume.id,
            company_name=request.company_name,
            role=request.role,
            start_date=request.start_date,
            end_date=request.end_date,
            description=request.description,
        )
        session.add(experience)
        session.flush()
        record = experience_record(experience)
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def update_experience(
    user_id: UUID,
    experience_id: UUID,
    request: ExperienceUpdateRequest,
    *,
    session: Session,
) -> ExperienceRecord:
    try:
        experience = _get_own_experience(user_id, experience_id, session)
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(experience, field, value)
        _ensure_valid_period(experience.start_date, experience.end_date)
        session.flush()
        record = experience_record(experience)
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def remove_experience(user_id: UUID, experience_id: UUID, *, session: Session) -> None:
    try:
        experience = _get_own_experience(user_id, experience_id, session)
        session.delete(experience)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _get_own_experience(
    user_id: UUID, experience_id: UUID, session: Session
) -> Experience:
    experience = session.scalar(
        select(Experience)
        .join(Resume, Resume.id == Experience.resume_id)
        .where(Experience.id == experience_id, Resume.candidate_id == user_id)
    )
    if experience is None:
        raise ExperienceNotFoundError()
    return experience


def _ensure_valid_period(start_date: date, end_date: date | None) -> None:
    if end_date is not None and end_date < start_date:
        raise InvalidExperiencePeriodError()
