from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.companies.exceptions import CompanyProfileNotFoundError
from app.db.models.company import Company
from app.profile_photos.domain.profile_photo import (
    PhotoTooLargeValueError,
    ProfilePhoto,
    UnsupportedPhotoValueError,
)
from app.profile_photos.exceptions import PhotoTooLargeError, UnsupportedPhotoTypeError
from app.storage.document_storage import DocumentStorage
from app.storage.removal import remove_quietly


def set_company_photo(
    user_id: UUID,
    filename: str | None,
    content: bytes,
    *,
    session: Session,
    storage: DocumentStorage,
) -> None:
    """Upload a new profile photo for the company, replacing any previous one.

    Mirrors ``set_candidate_photo`` in app/profile_photos/services/candidate_photo.py:
      1. Parse and validate (raises HTTP exception on error, no I/O touched).
      2. Fetch the company row with a row lock.
      3. PUT the object to storage (rollback + re-raise on failure).
      4. Write the five photo columns; commit.
         On DB failure: rollback then remove the just-uploaded object.
      5. If a previous object key existed, remove it quietly after the commit.
    """
    try:
        photo = ProfilePhoto.parse(filename, content)
    except PhotoTooLargeValueError as exc:
        raise PhotoTooLargeError from exc
    except UnsupportedPhotoValueError as exc:
        raise UnsupportedPhotoTypeError from exc

    try:
        company = session.get(Company, user_id, with_for_update=True)
        if company is None:
            session.rollback()
            raise CompanyProfileNotFoundError()
    except Exception:
        session.rollback()
        raise

    object_key = f"profile-photos/company/{user_id}/{uuid4()}"
    try:
        storage.put(object_key, photo.content, content_type=photo.content_type)
    except Exception:
        session.rollback()
        raise

    try:
        replaced_key = company.photo_object_key
        company.photo_object_key = object_key
        company.photo_filename = photo.filename
        company.photo_content_type = photo.content_type
        company.photo_size_bytes = len(photo.content)
        company.photo_uploaded_at = datetime.now(UTC)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        remove_quietly(storage, object_key)
        raise

    if replaced_key:
        remove_quietly(storage, replaced_key)


def remove_company_photo(
    user_id: UUID,
    *,
    session: Session,
    storage: DocumentStorage,
) -> None:
    """Remove the company's profile photo.

    Idempotent: if no photo exists, returns without error (caller returns 204).
    Mirrors ``remove_candidate_photo`` in app/profile_photos/services/candidate_photo.py.
    """
    try:
        company = session.get(Company, user_id, with_for_update=True)
        if company is None or company.photo_object_key is None:
            # No photo present — idempotent no-op.
            return
        object_key = company.photo_object_key
        company.photo_object_key = None
        company.photo_filename = None
        company.photo_content_type = None
        company.photo_size_bytes = None
        company.photo_uploaded_at = None
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    remove_quietly(storage, object_key)
