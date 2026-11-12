"""Integration tests for photo serving endpoints and photo_url on profile responses.

Covers:
- GET /api/v1/professionals/{candidate_id}/photo → 302 (photo exists), 404 (no photo),
  503 (storage unavailable)
- GET /api/v1/companies/{company_id}/photo → 302 (photo exists), 404 (no photo),
  503 (storage unavailable)
- photo_url on ProfessionalProfileResponse: non-null path when photo exists, null
  when no photo
- photo_url on CompanyProfileResponse: non-null path when photo exists, null when
  no photo
- Profile read with storage unavailable → 200, photo_url non-null (no signing at
  assembly time)

Requires a live PostgreSQL instance (RUN_DATABASE_INTEGRATION_TESTS=1).
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
from app.db.models.company import Company
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.storage.dependencies import get_document_storage
from tests.identity.fakes import FakeIdentityProvider
from tests.storage.fakes import FakeDocumentStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires PostgreSQL",
    ),
]

EMAIL_DOMAIN = "photo-serving.example.invalid"

PNG = b"\x89PNG\r\n\x1a\nsynthetic"


# ---------------------------------------------------------------------------
# Identity provider
# ---------------------------------------------------------------------------


class ServingIdentityProvider(FakeIdentityProvider):
    """Maps bearer token literal to a stable identity subject."""

    def verify_access_token(self, token: str) -> str:
        if token not in {
            "candidate",
            "other-candidate",
            "company",
            "other-company",
            "admin",
        }:
            raise InvalidAccessTokenError
        return f"serving-{token}"


def _auth(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(application: FastAPI) -> FakeDocumentStorage:
    fake = FakeDocumentStorage()
    application.dependency_overrides[get_identity_provider] = ServingIdentityProvider
    application.dependency_overrides[get_document_storage] = lambda: fake
    return fake


@pytest.fixture
def users() -> Iterator[dict[str, UUID]]:
    ids: dict[str, UUID] = {}
    with get_session_factory().begin() as session:
        # candidate
        user = AppUser(
            email=f"candidate@{EMAIL_DOMAIN}",
            identity_subject="serving-candidate",
            user_type=UserType.CANDIDATE,
        )
        session.add(user)
        session.flush()
        session.add(
            Candidate(
                id=user.id,
                full_name="Pessoa Sintética",
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1970, 1, 1),
                phone="51999990000",
            )
        )
        ids["candidate"] = user.id

        # other candidate (no photo)
        user2 = AppUser(
            email=f"other-candidate@{EMAIL_DOMAIN}",
            identity_subject="serving-other-candidate",
            user_type=UserType.CANDIDATE,
        )
        session.add(user2)
        session.flush()
        session.add(
            Candidate(
                id=user2.id,
                full_name="Outra Pessoa",
                cpf=f"{uuid4().int % 10**11:011d}",
                birth_date=date(1975, 6, 1),
                phone="51888880000",
            )
        )
        ids["other-candidate"] = user2.id

        # company
        user3 = AppUser(
            email=f"company@{EMAIL_DOMAIN}",
            identity_subject="serving-company",
            user_type=UserType.COMPANY,
        )
        session.add(user3)
        session.flush()
        session.add(
            Company(
                id=user3.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Empresa Sintética Ltda",
                corporate_email=user3.email,
                status=CompanyStatus.APPROVED,
            )
        )
        ids["company"] = user3.id

        # other company (no photo)
        user4 = AppUser(
            email=f"other-company@{EMAIL_DOMAIN}",
            identity_subject="serving-other-company",
            user_type=UserType.COMPANY,
        )
        session.add(user4)
        session.flush()
        session.add(
            Company(
                id=user4.id,
                cnpj=f"{uuid4().int % 10**14:014d}",
                legal_name="Outra Empresa Ltda",
                corporate_email=user4.email,
                status=CompanyStatus.APPROVED,
            )
        )
        ids["other-company"] = user4.id

        # admin
        user5 = AppUser(
            email=f"admin@{EMAIL_DOMAIN}",
            identity_subject="serving-admin",
            user_type=UserType.ADMINISTRATOR,
        )
        session.add(user5)
        session.flush()
        ids["admin"] = user5.id

    yield ids

    with get_session_factory().begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(ids.values())))


def _seed_candidate_photo(candidate_id: UUID) -> str:
    key = f"profile-photos/candidate/{candidate_id}/{uuid4()}"
    with get_session_factory().begin() as session:
        row = session.get(Candidate, candidate_id)
        assert row is not None
        row.photo_object_key = key
        row.photo_filename = "photo.png"
        row.photo_content_type = "image/png"
        row.photo_size_bytes = len(PNG)
        row.photo_uploaded_at = datetime.now(UTC)
    return key


def _seed_company_photo(company_id: UUID) -> str:
    key = f"profile-photos/company/{company_id}/{uuid4()}"
    with get_session_factory().begin() as session:
        row = session.get(Company, company_id)
        assert row is not None
        row.photo_object_key = key
        row.photo_filename = "logo.png"
        row.photo_content_type = "image/png"
        row.photo_size_bytes = len(PNG)
        row.photo_uploaded_at = datetime.now(UTC)
    return key


# ===========================================================================
# photo_url on profile responses — candidate
# ===========================================================================


def test_candidate_profile_with_photo_returns_photo_url_path(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """When a candidate has a photo, profile response photo_url is the serving path."""
    _seed_candidate_photo(users["candidate"])

    response = client.get("/api/v1/professionals/me", headers=_auth("candidate"))

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    expected_path = f"/api/v1/professionals/{users['candidate']}/photo"
    assert body["photo_url"] == expected_path


def test_candidate_profile_without_photo_returns_null_photo_url(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """When a candidate has no photo, profile response photo_url is null."""
    response = client.get("/api/v1/professionals/me", headers=_auth("other-candidate"))

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    assert body["photo_url"] is None


def test_candidate_profile_storage_unavailable_still_200_with_photo_url(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """Profile read with storage down must still return 200 with photo_url set.

    This is the critical invariant: assembly never signs a URL, so storage
    being unavailable cannot 503 a profile read.
    """
    _seed_candidate_photo(users["candidate"])
    storage.unavailable = True

    response = client.get("/api/v1/professionals/me", headers=_auth("candidate"))

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    # Must be the stable endpoint path, not null — storage down ≠ no photo.
    expected_path = f"/api/v1/professionals/{users['candidate']}/photo"
    assert body["photo_url"] == expected_path
    # Must NOT have called inline_url (assembly does not sign).
    assert "inline_url" not in storage.calls


# ===========================================================================
# photo_url on profile responses — company
# ===========================================================================


def test_company_profile_with_photo_returns_photo_url_path(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """When a company has a photo, profile response photo_url is the serving path."""
    _seed_company_photo(users["company"])

    response = client.get("/api/v1/companies/me/profile", headers=_auth("company"))

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    expected_path = f"/api/v1/companies/{users['company']}/photo"
    assert body["photo_url"] == expected_path


def test_company_profile_without_photo_returns_null_photo_url(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """When a company has no photo, profile response photo_url is null."""
    response = client.get(
        "/api/v1/companies/me/profile", headers=_auth("other-company")
    )

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    assert body["photo_url"] is None


def test_company_profile_storage_unavailable_still_200_with_photo_url(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """Company profile read with storage down must return 200 with photo_url set."""
    _seed_company_photo(users["company"])
    storage.unavailable = True

    response = client.get("/api/v1/companies/me/profile", headers=_auth("company"))

    assert response.status_code == 200
    body = response.json()
    assert "photo_url" in body
    expected_path = f"/api/v1/companies/{users['company']}/photo"
    assert body["photo_url"] == expected_path
    assert "inline_url" not in storage.calls


# ===========================================================================
# GET /api/v1/professionals/{candidate_id}/photo — serving endpoint
# ===========================================================================


def test_candidate_photo_serving_redirects_when_photo_exists(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """GET .../photo with stored photo → 302 to a presigned inline URL."""
    key = _seed_candidate_photo(users["candidate"])
    storage.objects[key] = (PNG, "image/png")

    response = client.get(
        f"/api/v1/professionals/{users['candidate']}/photo",
        headers=_auth("candidate"),
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://")
    assert "inline_url" in storage.calls


def test_candidate_photo_serving_404_when_no_photo(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """GET .../photo with no stored photo → 404."""
    response = client.get(
        f"/api/v1/professionals/{users['other-candidate']}/photo",
        headers=_auth("candidate"),
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_candidate_photo_serving_503_when_storage_unavailable(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """Serving endpoint with storage unavailable → 503 from the endpoint itself."""
    key = _seed_candidate_photo(users["candidate"])
    storage.objects[key] = (PNG, "image/png")
    storage.unavailable = True

    response = client.get(
        f"/api/v1/professionals/{users['candidate']}/photo",
        headers=_auth("candidate"),
        follow_redirects=False,
    )

    assert response.status_code == 503


# ===========================================================================
# GET /api/v1/companies/{company_id}/photo — serving endpoint
# ===========================================================================


def test_company_photo_serving_redirects_when_photo_exists(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """GET .../photo with stored photo → 302 to a presigned inline URL."""
    key = _seed_company_photo(users["company"])
    storage.objects[key] = (PNG, "image/png")

    response = client.get(
        f"/api/v1/companies/{users['company']}/photo",
        headers=_auth("company"),
        follow_redirects=False,
    )

    assert response.status_code == 302
    location = response.headers["Location"]
    assert location.startswith("https://")
    assert "inline_url" in storage.calls


def test_company_photo_serving_404_when_no_photo(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """GET .../photo with no stored photo → 404."""
    response = client.get(
        f"/api/v1/companies/{users['other-company']}/photo",
        headers=_auth("company"),
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_company_photo_serving_503_when_storage_unavailable(
    client: TestClient, storage: FakeDocumentStorage, users: dict[str, UUID]
) -> None:
    """Serving endpoint with storage unavailable → 503 from the endpoint itself."""
    key = _seed_company_photo(users["company"])
    storage.objects[key] = (PNG, "image/png")
    storage.unavailable = True

    response = client.get(
        f"/api/v1/companies/{users['company']}/photo",
        headers=_auth("company"),
        follow_redirects=False,
    )

    assert response.status_code == 503
