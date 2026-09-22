from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import (
    EducationNotFoundError,
    InvalidEducationPeriodError,
)
from app.candidates.schemas.education import (
    EducationCreateRequest,
    EducationUpdateRequest,
)
from app.candidates.services.records import EducationRecord, education_record
from app.candidates.services.resumes import get_or_create_resume
from app.db.models.education import Education
from app.db.models.resume import Resume


def add_education(
    user_id: UUID, request: EducationCreateRequest, *, session: Session
) -> EducationRecord:
    try:
        _ensure_valid_period(request.start_date, request.end_date)
        resume = get_or_create_resume(user_id, session)
        education = Education(
            resume_id=resume.id,
            institution=request.institution,
            degree=request.degree,
            field=request.field,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        session.add(education)
        session.flush()
        record = education_record(education)
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def update_education(
    user_id: UUID,
    education_id: UUID,
    request: EducationUpdateRequest,
    *,
    session: Session,
) -> EducationRecord:
    try:
        education = _get_own_education(user_id, education_id, session)
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(education, field, value)
        _ensure_valid_period(education.start_date, education.end_date)
        session.flush()
        record = education_record(education)
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def remove_education(user_id: UUID, education_id: UUID, *, session: Session) -> None:
    try:
        education = _get_own_education(user_id, education_id, session)
        session.delete(education)
        session.commit()
    except Exception:
        session.rollback()
        raise


def _get_own_education(
    user_id: UUID, education_id: UUID, session: Session
) -> Education:
    education = session.scalar(
        select(Education)
        .join(Resume, Resume.id == Education.resume_id)
        .where(Education.id == education_id, Resume.candidate_id == user_id)
    )
    if education is None:
        raise EducationNotFoundError()
    return education


def _ensure_valid_period(start_date: date | None, end_date: date | None) -> None:
    if start_date is not None and end_date is not None and end_date < start_date:
        raise InvalidEducationPeriodError()
