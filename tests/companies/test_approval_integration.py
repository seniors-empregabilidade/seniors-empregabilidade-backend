import os
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select

from app.auth.dependencies import require_approved_company
from app.db.models import AppUser, Company, Notification
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_DATABASE_INTEGRATION_TESTS") != "1", reason="requires PostgreSQL"
    ),
]


class ReviewIdentityProvider(FakeIdentityProvider):
    def verify_access_token(self, token: str) -> str:
        if token not in {"admin", "company", "candidate"}:
            raise InvalidAccessTokenError
        return f"review-{token}"


@pytest.fixture
def company_id(application: FastAPI) -> Iterator[UUID]:
    provider = ReviewIdentityProvider()
    application.dependency_overrides[get_identity_provider] = lambda: provider
    factory = get_session_factory()
    with factory.begin() as session:
        users = [
            AppUser(
                email=f"review-{role}@synthetic.example.invalid",
                identity_subject=f"review-{role}",
                user_type=user_type,
            )
            for role, user_type in [
                ("admin", UserType.ADMINISTRATOR),
                ("company", UserType.COMPANY),
                ("candidate", UserType.CANDIDATE),
            ]
        ]
        session.add_all(users)
        session.flush()
        company = Company(
            id=users[1].id,
            cnpj="11444777000161",
            legal_name="Synthetic Review Company",
            corporate_email=users[1].email,
            primary_cnae="6201501",
        )
        session.add(company)
        identifier = company.id
        user_ids = [user.id for user in users]
    yield identifier
    with factory.begin() as session:
        session.execute(delete(AppUser).where(AppUser.id.in_(user_ids)))


def authorization(role: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {role}"}


@pytest.mark.parametrize(
    "role,expected",
    [(None, 401), ("invalid", 401), ("company", 403), ("candidate", 403)],
)
def test_only_administrators_can_review(
    client: TestClient, company_id: UUID, role: str | None, expected: int
) -> None:
    response = client.patch(
        f"/api/v1/companies/{company_id}/approval",
        json={"status": "approved"},
        headers=authorization(role) if role else {},
    )
    assert response.status_code == expected
    with get_session_factory()() as session:
        assert (
            session.scalar(select(Company.status).where(Company.id == company_id))
            == CompanyStatus.PENDING
        )


def test_approval_unlocks_company_authorization(
    application: FastAPI, client: TestClient, company_id: UUID
) -> None:
    from fastapi import Depends

    @application.get(
        "/test-approved-company", dependencies=[Depends(require_approved_company)]
    )
    def protected() -> dict[str, bool]:
        return {"allowed": True}

    assert (
        client.get(
            "/test-approved-company", headers=authorization("company")
        ).status_code
        == 403
    )
    response = client.patch(
        f"/api/v1/companies/{company_id}/approval",
        json={"status": "approved"},
        headers=authorization("admin"),
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert (
        client.get(
            "/test-approved-company", headers=authorization("company")
        ).status_code
        == 200
    )
    assert (
        client.get("/api/v1/auth/me", headers=authorization("company")).json()[
            "company_status"
        ]
        == "approved"
    )


def test_rejection_notifies_owner_and_cannot_be_overwritten(
    client: TestClient, company_id: UUID
) -> None:
    path = f"/api/v1/companies/{company_id}/approval"
    response = client.patch(
        path,
        json={"status": "rejected", "reason": "Synthetic review reason"},
        headers=authorization("admin"),
    )
    assert response.status_code == 200
    own_status = client.get("/api/v1/companies/me", headers=authorization("company"))
    assert own_status.status_code == 200
    assert own_status.json() == {
        "id": str(company_id),
        "status": "rejected",
        "rejection_reason": "Synthetic review reason",
    }
    assert (
        client.get(
            "/api/v1/companies/me", headers=authorization("candidate")
        ).status_code
        == 403
    )
    assert (
        client.patch(
            path, json={"status": "approved"}, headers=authorization("admin")
        ).status_code
        == 409
    )
    with get_session_factory()() as session:
        notifications = session.scalars(
            select(Notification).where(Notification.user_id == company_id)
        ).all()
        assert len(notifications) == 1
        assert notifications[0].message == "Synthetic review reason"
        assert notifications[0].read is False


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "rejected"},
        {"status": "rejected", "reason": "  "},
        {"status": "blocked"},
        {"status": "approved", "reason": "unexpected"},
    ],
)
def test_invalid_decision_does_not_change_company(
    client: TestClient, company_id: UUID, payload: dict[str, str]
) -> None:
    response = client.patch(
        f"/api/v1/companies/{company_id}/approval",
        json=payload,
        headers=authorization("admin"),
    )
    assert response.status_code == 422
    with get_session_factory()() as session:
        assert (
            session.scalar(select(Company.status).where(Company.id == company_id))
            == CompanyStatus.PENDING
        )


def test_approval_rechecks_blocked_segments(
    client: TestClient, company_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "blocked_cnae_prefixes", ["62"])
    response = client.patch(
        f"/api/v1/companies/{company_id}/approval",
        json={"status": "approved"},
        headers=authorization("admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "company_segment_blocked"
    with get_session_factory()() as session:
        assert (
            session.scalar(select(Company.status).where(Company.id == company_id))
            == CompanyStatus.PENDING
        )


def test_concurrent_decisions_create_only_one_rejection_notification(
    client: TestClient, company_id: UUID
) -> None:
    def submit(_: int) -> int:
        return client.patch(
            f"/api/v1/companies/{company_id}/approval",
            json={"status": "rejected", "reason": "Synthetic reason"},
            headers=authorization("admin"),
        ).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(submit, range(2))) == [200, 409]
    with get_session_factory()() as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == company_id)
            )
            == 1
        )


def test_notification_failure_rolls_back_rejection(
    client: TestClient, company_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy import event
    from sqlalchemy.orm import Session

    def reject_notification_flush(session: Session, *_: object) -> None:
        if any(isinstance(row, Notification) for row in session.new):
            raise RuntimeError("Synthetic notification persistence failure")

    event.listen(Session, "before_flush", reject_notification_flush)
    try:
        response = client.patch(
            f"/api/v1/companies/{company_id}/approval",
            json={"status": "rejected", "reason": "Synthetic reason"},
            headers=authorization("admin"),
        )
    finally:
        event.remove(Session, "before_flush", reject_notification_flush)
    assert response.status_code == 500
    with get_session_factory()() as session:
        assert (
            session.scalar(select(Company.status).where(Company.id == company_id))
            == CompanyStatus.PENDING
        )
        assert (
            session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.user_id == company_id)
            )
            == 0
        )


def test_unknown_company_is_not_found(client: TestClient, company_id: UUID) -> None:
    from uuid import uuid4

    response = client.patch(
        f"/api/v1/companies/{uuid4()}/approval",
        json={"status": "approved"},
        headers=authorization("admin"),
    )
    assert response.status_code == 404
    assert response.json()["code"] == "company_not_found"


def test_missing_activity_cannot_be_approved(
    client: TestClient, company_id: UUID
) -> None:
    with get_session_factory().begin() as session:
        company = session.get(Company, company_id)
        assert company is not None
        company.primary_cnae = None
    response = client.patch(
        f"/api/v1/companies/{company_id}/approval",
        json={"status": "approved"},
        headers=authorization("admin"),
    )
    assert response.status_code == 422
    assert response.json()["code"] == "company_activity_required"


def test_pending_company_can_read_own_status(
    client: TestClient, company_id: UUID
) -> None:
    response = client.get("/api/v1/companies/me", headers=authorization("company"))
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "id": str(company_id),
        "status": "pending",
        "rejection_reason": None,
    }
