from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.candidates.exceptions import (
    CertificationNotFoundError,
    InvalidCertificationPeriodError,
)
from app.candidates.schemas.certification import (
    CertificationCreateRequest,
    CertificationUpdateRequest,
)
from app.candidates.services.records import CertificationRecord, certification_record
from app.candidates.services.resumes import get_or_create_resume
from app.db.models.attached_certificate import AttachedCertificate
from app.db.models.certification import Certification
from app.db.models.resume import Resume
from app.storage.document_storage import DocumentStorage
from app.storage.removal import remove_quietly


def add_certification(
    user_id: UUID, request: CertificationCreateRequest, *, session: Session
) -> CertificationRecord:
    try:
        _ensure_valid_period(request.issued_date, request.expiration_date)
        resume = get_or_create_resume(user_id, session)
        certification = Certification(
            resume_id=resume.id,
            name=request.name,
            issuer=request.issuer,
            issued_date=request.issued_date,
            expiration_date=request.expiration_date,
        )
        session.add(certification)
        session.flush()
        record = certification_record(certification, None)
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def update_certification(
    user_id: UUID,
    certification_id: UUID,
    request: CertificationUpdateRequest,
    *,
    session: Session,
) -> CertificationRecord:
    try:
        certification = get_own_certification(user_id, certification_id, session)
        for field, value in request.model_dump(exclude_unset=True).items():
            setattr(certification, field, value)
        _ensure_valid_period(certification.issued_date, certification.expiration_date)
        session.flush()
        record = certification_record(
            certification, attached_document(certification.id, session)
        )
        session.commit()
        return record
    except Exception:
        session.rollback()
        raise


def remove_certification(
    user_id: UUID,
    certification_id: UUID,
    *,
    session: Session,
    storage: DocumentStorage,
) -> None:
    try:
        certification = get_own_certification(
            user_id, certification_id, session, lock=True
        )
        document = attached_document(certification.id, session)
        object_key = document.object_key if document else None
        session.delete(certification)
        session.commit()
    except Exception:
        session.rollback()
        raise
    if object_key:
        remove_quietly(storage, object_key)


def get_own_certification(
    user_id: UUID, certification_id: UUID, session: Session, *, lock: bool = False
) -> Certification:
    query = (
        select(Certification)
        .join(Resume, Resume.id == Certification.resume_id)
        .where(Certification.id == certification_id, Resume.candidate_id == user_id)
    )
    certification = session.scalar(
        query.with_for_update(of=Certification) if lock else query
    )
    if certification is None:
        raise CertificationNotFoundError()
    return certification


def attached_document(
    certification_id: UUID, session: Session
) -> AttachedCertificate | None:
    return session.scalar(
        select(AttachedCertificate).where(
            AttachedCertificate.certification_id == certification_id
        )
    )


def _ensure_valid_period(
    issued_date: date | None, expiration_date: date | None
) -> None:
    if (
        issued_date is not None
        and expiration_date is not None
        and expiration_date < issued_date
    ):
        raise InvalidCertificationPeriodError()
