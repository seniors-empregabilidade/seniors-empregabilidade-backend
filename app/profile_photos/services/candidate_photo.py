from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.candidates.exceptions import ProfileNotFoundError
from app.db.models.candidate import Candidate
from app.profile_photos.domain.profile_photo import (
    PhotoTooLargeValueError,
    ProfilePhoto,
    UnsupportedPhotoValueError,
)
from app.profile_photos.exceptions import PhotoTooLargeError, UnsupportedPhotoTypeError
from app.storage.document_storage import DocumentStorage
from app.storage.removal import remove_quietly


def set_candidate_photo(
    user_id: UUID,
    filename: str | None,
    content: bytes,
    *,
    session: Session,
    storage: DocumentStorage,
) -> None:
    """Upload a new profile photo for the candidate, replacing any previous one.

    Mirrors ``attach_document`` in app/candidates/services/certification_documents.py:
      1. Parse and validate (raises HTTP exception on error, no I/O touched).
      2. Fetch the candidate row with a row lock.
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
        candidate = session.get(Candidate, user_id, with_for_update=True)
        if candidate is None:
            session.rollback()
            raise ProfileNotFoundError()
    except Exception:
        session.rollback()
        raise

    object_key = f"profile-photos/candidate/{user_id}/{uuid4()}"
    try:
        storage.put(object_key, photo.content, content_type=photo.content_type)
    except Exception:
        session.rollback()
        raise

    try:
        replaced_key = candidate.photo_object_key
        candidate.photo_object_key = object_key
        candidate.photo_filename = photo.filename
        candidate.photo_content_type = photo.content_type
        candidate.photo_size_bytes = len(photo.content)
        candidate.photo_uploaded_at = datetime.now(UTC)
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        remove_quietly(storage, object_key)
        raise

    if replaced_key:
        remove_quietly(storage, replaced_key)


def remove_candidate_photo(
    user_id: UUID,
    *,
    session: Session,
    storage: DocumentStorage,
) -> None:
    """Remove the candidate's profile photo.

    Idempotent: if no photo exists, returns without error (caller returns 204).
    Mirrors ``remove_document`` in app/candidates/services/certification_documents.py.
    """
    try:
        candidate = session.get(Candidate, user_id, with_for_update=True)
        if candidate is None or candidate.photo_object_key is None:
            # No photo present — idempotent no-op.
            return
        object_key = candidate.photo_object_key
        candidate.photo_object_key = None
        candidate.photo_filename = None
        candidate.photo_content_type = None
        candidate.photo_size_bytes = None
        candidate.photo_uploaded_at = None
        session.flush()
        session.commit()
    except Exception:
        session.rollback()
        raise

    remove_quietly(storage, object_key)
