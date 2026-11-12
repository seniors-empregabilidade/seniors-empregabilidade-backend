"""Integration tests for PUT /me/photo and DELETE /me/photo endpoints.

Requires a live PostgreSQL instance (RUN_DATABASE_INTEGRATION_TESTS=1).

NOTE on photo_url: ProfessionalProfileResponse does not have a photo_url field yet
(that is added in Task 6).  These tests assert the stored photo via the candidate
row's photo_object_key column rather than via a response field, and assert 200/204
status codes as the primary correctness signal.
"""

import os
from collections.abc import Iterator
from datetime import UTC, date, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models.app_user import AppUser
from app.db.models.candidate import Candidate
from app.db.models.enums import UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.profile_photos.domain.profile_photo import MAX_PHOTO_BYTES
from app.storage.dependencies import get_document_storage
from tests.identity.fakes import FakeIdentityProvider
from tests.storage.fakes import FakeDocumentStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]

PATH = "/api/v1/professionals/me/photo"
EMAIL_DOMAIN = "photo-router.example.invalid"

PNG = b"\x89PNG\r\n\x1a\nsynthetic"
PDF = b"%PDF-1.7\nsynthetic"


# ---------------------------------------------------------------------------
# Identity provider that maps bearer token to a stable subject string
# ---------------------------------------------------------------------------


class RoleIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"owner", "other", "admin", "company"}:
            raise InvalidAccessTokenError
        return f"photo-{token}"


def auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(application: FastAPI) -> FakeDocumentStorage:
    fake = FakeDocumentStorage()
    application.dependency_overrides[get_identity_provider] = RoleIdentityProvider
    application.dependency_overrides[get_document_storage] = lambda: fake
    return fake


@pytest.fixture
def users() -> Iterator[dict[str, UUID]]:
    ids: dict[str, UUID] = {}
    with get_session_factory().begin() as session:
        for role, user_type in [
            ("owner", UserType.CANDIDATE),
            ("other", UserType.CANDIDATE),
            ("admin", UserType.ADMINISTRATOR),
            ("company", UserType.COMPANY),
        ]:
            user = AppUser(
                email=f"{role}@{EMAIL_DOMAIN}",
                identity_subject=f"photo-{role}",
                user_type=user_type,
            )
            session.add(user)
            session.flush()
            if user_type == UserType.CANDIDATE:
                session.add(
                    Candidate(
                        id=user.id,
                        full_name="Pessoa Sintética",
                        cpf=f"{uuid4().int % 10**11:011d}",
                        birth_date=date(1970, 1, 1),
                        phone="51999990000",
                    )
                )
            ids[role] = user.id
    yield ids
    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(ids.values())))


def _row(user_id: UUID) -> Candidate | None:
    with get_session_factory()() as s:
        return s.get(Candidate, user_id)


def _seed_photo(user_id: UUID) -> str:
    """Insert a photo record directly and return the object key."""
    key = f"profile-photos/candidate/{user_id}/{uuid4()}"
    with get_session_factory().begin() as session:
        candidate = session.get(Candidate, user_id)
        assert candidate is not None
        candidate.photo_object_key = key
        candidate.photo_filename = "existing.png"
        candidate.photo_content_type = "image/png"
        candidate.photo_size_bytes = len(PNG)
        candidate.photo_uploaded_at = datetime.now(UTC)
    return key


# ---------------------------------------------------------------------------
# PUT /me/photo - happy path
# ---------------------------------------------------------------------------


def test_put_valid_png_returns_200_and_profile(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.put(
        PATH,
        files={"file": ("photo.png", PNG, "image/png")},
        headers=auth("owner"),
    )

    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    # ProfessionalProfileResponse has id and full_name at minimum.
    body = response.json()
    assert body["id"] == str(users["owner"])
    assert body["full_name"] == "Pessoa Sintética"

    # The photo must be persisted on the candidate row.
    row = _row(users["owner"])
    assert row is not None
    assert row.photo_object_key is not None
    assert row.photo_object_key.startswith(
        f"profile-photos/candidate/{users['owner']}/"
    )
    assert storage.objects[row.photo_object_key] == (PNG, "image/png")


def test_put_replaces_previous_photo_and_removes_old_object(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    old_key = _seed_photo(users["owner"])
    storage.objects[old_key] = (PNG, "image/png")

    response = client.put(
        PATH,
        files={"file": ("new.png", PNG, "image/png")},
        headers=auth("owner"),
    )

    assert response.status_code == 200
    row = _row(users["owner"])
    assert row is not None
    new_key = row.photo_object_key
    assert new_key is not None
    assert new_key != old_key
    assert old_key not in storage.objects
    assert new_key in storage.objects


# ---------------------------------------------------------------------------
# PUT /me/photo - validation errors
# ---------------------------------------------------------------------------


def test_put_oversized_file_returns_422_photo_too_large(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    oversized = PNG + b"\x00" * MAX_PHOTO_BYTES  # one byte past the limit

    response = client.put(
        PATH,
        files={"file": ("big.png", oversized, "image/png")},
        headers=auth("owner"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "photo_too_large"
    assert "file" in response.json()["errors"]
    assert storage.calls == []


def test_put_disguised_pdf_returns_422_unsupported_photo_type(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.put(
        PATH,
        files={"file": ("trick.png", PDF, "image/png")},
        headers=auth("owner"),
    )

    assert response.status_code == 422
    assert response.json()["code"] == "unsupported_photo_type"
    assert "file" in response.json()["errors"]
    assert storage.calls == []


# ---------------------------------------------------------------------------
# DELETE /me/photo - happy path
# ---------------------------------------------------------------------------


def test_delete_photo_returns_204_and_clears_row(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    key = _seed_photo(users["owner"])
    storage.objects[key] = (PNG, "image/png")

    response = client.delete(PATH, headers=auth("owner"))

    assert response.status_code == 204
    row = _row(users["owner"])
    assert row is not None
    assert row.photo_object_key is None
    assert key not in storage.objects


def test_delete_without_photo_is_idempotent_204(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """DELETE when no photo exists must return 204 (idempotent)."""
    response = client.delete(PATH, headers=auth("owner"))

    assert response.status_code == 204
    assert storage.calls == []


# ---------------------------------------------------------------------------
# Authorization guards
# ---------------------------------------------------------------------------


def test_put_unauthenticated_returns_401(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    response = client.put(PATH, files={"file": ("photo.png", PNG, "image/png")})
    assert response.status_code == 401


def test_delete_unauthenticated_returns_401(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    assert client.delete(PATH).status_code == 401


def test_put_non_candidate_role_returns_403(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    for role in ("admin", "company"):
        response = client.put(
            PATH,
            files={"file": ("photo.png", PNG, "image/png")},
            headers=auth(role),
        )
        assert response.status_code == 403, f"expected 403 for role={role}"


def test_delete_non_candidate_role_returns_403(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    for role in ("admin", "company"):
        assert client.delete(PATH, headers=auth(role)).status_code == 403


def test_unavailable_storage_returns_503_and_does_not_persist(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    storage.unavailable = True

    response = client.put(
        PATH,
        files={"file": ("photo.png", PNG, "image/png")},
        headers=auth("owner"),
    )

    assert response.status_code == 503
    row = _row(users["owner"])
    assert row is not None
    assert row.photo_object_key is None
