"""Integration tests for photo_url on company-facing candidate screens.

Covers:
- Ranking (GET /api/v1/jobs/{job_id}/applications):
  - A candidate with a photo → profile.photo_url is the /professionals/{id}/photo path.
  - A candidate without a photo → profile.photo_url is null.
  - Storage unavailable while assembling → still 200, photo_url non-null (no signing at
    assembly time).
- Applicant detail (GET /api/v1/applications/{application_id}/profile):
  - A candidate with a photo → photo_url is the /professionals/{id}/photo path.
  - A candidate without a photo → photo_url is null.

Requires a live PostgreSQL instance (RUN_DATABASE_INTEGRATION_TESTS=1).
"""

import os
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Application
from app.db.models.candidate import Candidate
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.storage.dependencies import get_document_storage
from tests.identity.fakes import FakeIdentityProvider
from tests.jobs.conftest import (
    MANAGE_JOBS_OWNER_TOKEN,
    ManageJobsScenario,
    manage_jobs_authorization,
)
from tests.storage.fakes import FakeDocumentStorage

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1",
        reason="requires PostgreSQL",
    ),
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def storage(application: FastAPI) -> FakeDocumentStorage:
    fake = FakeDocumentStorage()
    application.dependency_overrides[get_document_storage] = lambda: fake
    return fake


@pytest.fixture
def ranking_client(
    application: FastAPI,
    database_session: Session,
    storage: FakeDocumentStorage,
) -> Iterator[TestClient]:
    """TestClient wired to a ManageJobsIdentityProvider for ranking tests."""

    class RankingIdentityProvider(FakeIdentityProvider):
        def verify_access_token(self, token: str) -> str:
            if token == MANAGE_JOBS_OWNER_TOKEN:
                return "subject-manage-jobs-owner"
            raise InvalidAccessTokenError

    application.dependency_overrides[get_session] = lambda: database_session
    provider = RankingIdentityProvider()
    application.dependency_overrides[get_identity_provider] = lambda: provider
    with TestClient(application, raise_server_exceptions=False) as client:
        yield client
    application.dependency_overrides.clear()


def _give_photo(session: Session, candidate_id: UUID) -> str:
    """Set photo_object_key on an existing Candidate row and return the key."""
    key = f"profile-photos/candidate/{candidate_id}/{uuid4()}"
    row = session.get(Candidate, candidate_id)
    assert row is not None
    row.photo_object_key = key
    row.photo_filename = "photo.png"
    row.photo_content_type = "image/png"
    row.photo_size_bytes = 42
    row.photo_uploaded_at = datetime.now(UTC)
    session.commit()
    return key


def _applicant_id_for(session: Session, job_id: UUID, candidate_id: UUID) -> UUID:
    identifier = session.scalar(
        select(Application.id).where(
            Application.job_id == job_id,
            Application.candidate_id == candidate_id,
        )
    )
    assert identifier is not None
    return identifier


# ===========================================================================
# Ranking — photo_url on profile
# ===========================================================================


def test_ranking_candidate_with_photo_has_photo_url_path(
    ranking_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    """A ranked candidate with a photo has profile.photo_url = serving path."""
    _give_photo(database_session, manage_jobs_scenario.candidate_one_id)

    response = ranking_client.get(
        f"/api/v1/jobs/{manage_jobs_scenario.open_job_id}/applications",
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    applicants = response.json()["applicants"]
    with_photo = next(
        a
        for a in applicants
        if a["profile"]["candidate_id"] == str(manage_jobs_scenario.candidate_one_id)
    )
    expected = f"/api/v1/professionals/{manage_jobs_scenario.candidate_one_id}/photo"
    assert with_photo["profile"]["photo_url"] == expected


def test_ranking_candidate_without_photo_has_null_photo_url(
    ranking_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    """A ranked candidate without a photo has profile.photo_url = null."""
    # candidate_two has no photo (default scenario)
    response = ranking_client.get(
        f"/api/v1/jobs/{manage_jobs_scenario.open_job_id}/applications",
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    applicants = response.json()["applicants"]
    without_photo = next(
        a
        for a in applicants
        if a["profile"]["candidate_id"] == str(manage_jobs_scenario.candidate_two_id)
    )
    assert without_photo["profile"]["photo_url"] is None


def test_ranking_storage_unavailable_still_200_no_signing(
    ranking_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
    storage: FakeDocumentStorage,
) -> None:
    """Assembling the ranking with storage unavailable must NOT 503.

    photo_url_for never calls storage; only the serving endpoint signs.
    """
    _give_photo(database_session, manage_jobs_scenario.candidate_one_id)
    storage.unavailable = True

    response = ranking_client.get(
        f"/api/v1/jobs/{manage_jobs_scenario.open_job_id}/applications",
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    applicants = response.json()["applicants"]
    with_photo = next(
        a
        for a in applicants
        if a["profile"]["candidate_id"] == str(manage_jobs_scenario.candidate_one_id)
    )
    expected = f"/api/v1/professionals/{manage_jobs_scenario.candidate_one_id}/photo"
    assert with_photo["profile"]["photo_url"] == expected
    # Assembly must not have called storage.
    assert "inline_url" not in storage.calls


# ===========================================================================
# Applicant detail — photo_url
# ===========================================================================


def test_applicant_detail_with_photo_has_photo_url_path(
    ranking_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    """Applicant detail with a photo returns photo_url = serving path."""
    _give_photo(database_session, manage_jobs_scenario.candidate_one_id)
    application_id = _applicant_id_for(
        database_session,
        manage_jobs_scenario.open_job_id,
        manage_jobs_scenario.candidate_one_id,
    )

    response = ranking_client.get(
        f"/api/v1/applications/{application_id}/profile",
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    expected = f"/api/v1/professionals/{manage_jobs_scenario.candidate_one_id}/photo"
    assert body["photo_url"] == expected


def test_applicant_detail_without_photo_has_null_photo_url(
    ranking_client: TestClient,
    database_session: Session,
    manage_jobs_scenario: ManageJobsScenario,
) -> None:
    """Applicant detail without a photo returns photo_url = null."""
    # candidate_two has no photo
    application_id = _applicant_id_for(
        database_session,
        manage_jobs_scenario.open_job_id,
        manage_jobs_scenario.candidate_two_id,
    )

    response = ranking_client.get(
        f"/api/v1/applications/{application_id}/profile",
        headers=manage_jobs_authorization(MANAGE_JOBS_OWNER_TOKEN),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["photo_url"] is None
