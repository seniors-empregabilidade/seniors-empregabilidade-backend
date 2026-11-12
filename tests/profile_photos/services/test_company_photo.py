"""Integration tests for set_company_photo / remove_company_photo.

Requires a live PostgreSQL instance (RUN_DATABASE_INTEGRATION_TESTS=1).

Design note: tests that exercise cross-session visibility (replace, remove)
create and read data through get_session_factory().begin() so that real
commits reach the database and are visible from independent connections.
Tests that only need single-session correctness use the database_session
fixture, which wraps the test in a rolled-back outer transaction.
"""

import os
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event
from sqlalchemy.orm import Session

from app.db.models.app_user import AppUser
from app.db.models.company import Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session_factory
from app.profile_photos.exceptions import PhotoTooLargeError, UnsupportedPhotoTypeError
from app.profile_photos.services.company_photo import (
    remove_company_photo,
    set_company_photo,
)
from app.storage.exceptions import DocumentStorageUnavailableError
from tests.storage.fakes import FakeDocumentStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

PNG = b"\x89PNG\r\n\x1a\nsynthetic"
JPEG = b"\xff\xd8\xff\xe0synthetic"
PDF = b"%PDF-1.7\nsynthetic"
MAX_PHOTO_BYTES = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_company_in_session(session: Session) -> AppUser:
    """Create a user + company row and flush (does not commit)."""
    user = AppUser(
        email=f"{uuid4().hex}@photo-company-svc.example.invalid",
        identity_subject=uuid4().hex,
        user_type=UserType.COMPANY,
    )
    session.add(user)
    session.flush()
    session.add(
        Company(
            id=user.id,
            cnpj=f"{uuid4().int % 10**14:014d}",
            legal_name="Empresa Sintética Ltda",
            corporate_email=user.email,
            status=CompanyStatus.APPROVED,
        )
    )
    session.flush()
    return user


def _create_committed_company() -> tuple[UUID, UUID]:
    """Create user + company with a real commit; return (user_id, user_id)."""
    with get_session_factory().begin() as session:
        user = AppUser(
            email=f"{uuid4().hex}@photo-company-svc.example.invalid",
            identity_subject=uuid4().hex,
            user_type=UserType.COMPANY,
        )
        session.add(user)
        session.flush()
        session.add(
            Company(
                id=user.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Empresa Sintética Ltda",
                corporate_email=user.email,
                status=CompanyStatus.APPROVED,
            )
        )
        return user.id, user.id


def _delete_user(user_id: UUID) -> None:
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.id == user_id))


def _fresh_row(user_id: UUID) -> Company | None:
    with get_session_factory()() as s:
        return s.get(Company, user_id)


# ---------------------------------------------------------------------------
# set_company_photo - happy path (single-session, savepoint-based)
# ---------------------------------------------------------------------------


def test_set_stores_object_and_fills_all_columns(database_session: Session) -> None:
    user = _create_company_in_session(database_session)
    storage = FakeDocumentStorage()

    set_company_photo(
        user.id, "photo.png", PNG, session=database_session, storage=storage
    )

    database_session.expire_all()
    row = database_session.get(Company, user.id)
    assert row is not None
    assert row.photo_object_key is not None
    assert row.photo_object_key.startswith(f"profile-photos/company/{user.id}/")
    assert row.photo_filename == "photo.png"
    assert row.photo_content_type == "image/png"
    assert row.photo_size_bytes == len(PNG)
    assert row.photo_uploaded_at is not None
    assert storage.objects[row.photo_object_key] == (PNG, "image/png")


# ---------------------------------------------------------------------------
# set_company_photo - replace removes previous key (cross-session)
# ---------------------------------------------------------------------------


def test_set_replace_removes_previous_key_after_commit() -> None:
    user_id, _ = _create_committed_company()
    storage = FakeDocumentStorage()
    try:
        # First upload — real commit so the key lands in the DB.
        with get_session_factory().begin() as session1:
            set_company_photo(
                user_id, "first.png", PNG, session=session1, storage=storage
            )

        old_key = _fresh_row(user_id)
        assert old_key is not None
        first_key = old_key.photo_object_key
        assert first_key is not None
        storage.objects[first_key] = (PNG, "image/png")

        # Second upload — replaces the first.
        with get_session_factory().begin() as session2:
            set_company_photo(
                user_id, "second.png", JPEG, session=session2, storage=storage
            )

        row = _fresh_row(user_id)
        assert row is not None
        second_key = row.photo_object_key
        assert second_key is not None
        assert second_key != first_key
        assert first_key not in storage.objects
        assert second_key in storage.objects
    finally:
        _delete_user(user_id)


# ---------------------------------------------------------------------------
# set_company_photo - validation errors (raised before any I/O)
# ---------------------------------------------------------------------------


def test_set_oversized_photo_raises_photo_too_large(database_session: Session) -> None:
    user = _create_company_in_session(database_session)
    storage = FakeDocumentStorage()
    oversized = PNG + b"\x00" * MAX_PHOTO_BYTES

    with pytest.raises(PhotoTooLargeError):
        set_company_photo(
            user.id, "big.png", oversized, session=database_session, storage=storage
        )

    assert storage.calls == []
    row = database_session.get(Company, user.id)
    assert row is not None
    assert row.photo_object_key is None


def test_set_disguised_pdf_raises_unsupported_photo_type(
    database_session: Session,
) -> None:
    user = _create_company_in_session(database_session)
    storage = FakeDocumentStorage()

    with pytest.raises(UnsupportedPhotoTypeError):
        set_company_photo(
            user.id, "trick.png", PDF, session=database_session, storage=storage
        )

    assert storage.calls == []
    row = database_session.get(Company, user.id)
    assert row is not None
    assert row.photo_object_key is None


# ---------------------------------------------------------------------------
# set_company_photo - storage failure rolls back columns (cross-session)
# ---------------------------------------------------------------------------


def test_storage_put_failure_leaves_columns_unchanged() -> None:
    user_id, _ = _create_committed_company()
    storage = FakeDocumentStorage()
    storage.unavailable = True
    try:
        with (
            pytest.raises(DocumentStorageUnavailableError),
            get_session_factory().begin() as session,
        ):
            set_company_photo(
                user_id, "photo.png", PNG, session=session, storage=storage
            )

        row = _fresh_row(user_id)
        assert row is not None
        assert row.photo_object_key is None
    finally:
        _delete_user(user_id)


# ---------------------------------------------------------------------------
# set_company_photo - DB failure removes the already-uploaded object
# ---------------------------------------------------------------------------


def test_db_failure_after_storage_removes_uploaded_object(
    database_session: Session,
) -> None:
    user = _create_company_in_session(database_session)
    storage = FakeDocumentStorage()

    def _reject_photo_dirty(session: Session, *_: object) -> None:
        for obj in session.dirty:
            if isinstance(obj, Company) and obj.photo_object_key is not None:
                raise RuntimeError("Synthetic DB failure on photo write")

    event.listen(Session, "before_flush", _reject_photo_dirty)
    try:
        with pytest.raises(RuntimeError):
            set_company_photo(
                user.id, "photo.png", PNG, session=database_session, storage=storage
            )
    finally:
        event.remove(Session, "before_flush", _reject_photo_dirty)

    assert storage.calls == ["put", "delete"]
    assert storage.objects == {}


# ---------------------------------------------------------------------------
# remove_company_photo - happy path (cross-session)
# ---------------------------------------------------------------------------


def test_remove_clears_all_columns_and_deletes_storage_object() -> None:
    user_id, _ = _create_committed_company()
    storage = FakeDocumentStorage()
    existing_key = f"profile-photos/company/{user_id}/{uuid4()}"
    try:
        # Seed a photo on the row with a real commit.
        with get_session_factory().begin() as session:
            company = session.get(Company, user_id)
            assert company is not None
            company.photo_object_key = existing_key
            company.photo_filename = "old.png"
            company.photo_content_type = "image/png"
            company.photo_size_bytes = len(PNG)
            company.photo_uploaded_at = datetime.now(UTC)
        storage.objects[existing_key] = (PNG, "image/png")

        # Remove via an independent session.
        with get_session_factory().begin() as session2:
            remove_company_photo(user_id, session=session2, storage=storage)

        row = _fresh_row(user_id)
        assert row is not None
        assert row.photo_object_key is None
        assert row.photo_filename is None
        assert row.photo_content_type is None
        assert row.photo_size_bytes is None
        assert row.photo_uploaded_at is None
        assert existing_key not in storage.objects
    finally:
        _delete_user(user_id)


# ---------------------------------------------------------------------------
# remove_company_photo - idempotent when no photo exists
# ---------------------------------------------------------------------------


def test_remove_when_no_photo_is_a_noop(database_session: Session) -> None:
    """DELETE /me/photo with no photo is a no-op (idempotent - does not raise)."""
    user = _create_company_in_session(database_session)
    storage = FakeDocumentStorage()

    remove_company_photo(user.id, session=database_session, storage=storage)

    assert storage.calls == []
    row = database_session.get(Company, user.id)
    assert row is not None
    assert row.photo_object_key is None
