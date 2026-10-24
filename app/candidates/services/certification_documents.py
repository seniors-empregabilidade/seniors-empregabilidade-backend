from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.candidates.domain.certificate_document import (
    CertificateDocument,
    DocumentTooLargeValueError,
    UnsupportedDocumentValueError,
)
from app.candidates.exceptions import (
    CertificationDocumentNotFoundError,
    DocumentTooLargeError,
    UnsupportedDocumentTypeError,
)
from app.candidates.services.certifications import (
    attached_document,
    get_own_certification,
)
from app.candidates.services.records import CertificationRecord, certification_record
from app.db.models.attached_certificate import AttachedCertificate
from app.storage.document_storage import DocumentStorage
from app.storage.removal import remove_quietly

LINK_LIFETIME: Final = timedelta(minutes=5)


@dataclass(frozen=True, slots=True)
class DocumentLink:
    url: str
    expires_at: datetime


def attach_document(
    user_id: UUID,
    certification_id: UUID,
    filename: str | None,
    content: bytes,
    *,
    session: Session,
    storage: DocumentStorage,
) -> CertificationRecord:
    try:
        document = CertificateDocument.parse(filename, content)
    except DocumentTooLargeValueError as exc:
        raise DocumentTooLargeError from exc
    except UnsupportedDocumentValueError as exc:
        raise UnsupportedDocumentTypeError from exc

    try:
        # The row lock serializes concurrent uploads to the same certification.
        certification = get_own_certification(
            user_id, certification_id, session, lock=True
        )
    except Exception:
        session.rollback()
        raise

    object_key = f"certifications/{certification.id}/{uuid4()}"
    try:
        storage.put(object_key, document.content, content_type=document.content_type)
    except Exception:
        session.rollback()
        raise

    try:
        attached = attached_document(certification.id, session)
        replaced_key = attached.object_key if attached else None
        if attached is None:
            attached = AttachedCertificate(certification_id=certification.id)
            session.add(attached)
        attached.object_key = object_key
        attached.filename = document.filename
        attached.content_type = document.content_type
        attached.size_bytes = len(document.content)
        attached.uploaded_at = datetime.now(UTC)
        session.flush()
        record = certification_record(certification, attached)
        session.commit()
    except Exception:
        session.rollback()
        remove_quietly(storage, object_key)
        raise
    if replaced_key:
        remove_quietly(storage, replaced_key)
    return record


def remove_document(
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
        attached = attached_document(certification.id, session)
        if attached is None:
            raise CertificationDocumentNotFoundError()
        object_key = attached.object_key
        session.delete(attached)
        session.commit()
    except Exception:
        session.rollback()
        raise
    remove_quietly(storage, object_key)


def document_link(
    professional_id: UUID,
    certification_id: UUID,
    *,
    session: Session,
    storage: DocumentStorage,
) -> DocumentLink:
    certification = get_own_certification(professional_id, certification_id, session)
    return _link(attached_document(certification.id, session), storage)


def _link(
    attached: AttachedCertificate | None, storage: DocumentStorage
) -> DocumentLink:
    if attached is None:
        raise CertificationDocumentNotFoundError()
    expires_at = datetime.now(UTC) + LINK_LIFETIME
    url = storage.download_url(
        attached.object_key,
        filename=attached.filename,
        content_type=attached.content_type,
        expires_in=int(LINK_LIFETIME.total_seconds()),
    )
    return DocumentLink(url=url, expires_at=expires_at)
