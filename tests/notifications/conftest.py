from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import ClassVar
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.db.models import AppUser, Notification
from app.db.models.enums import UserType
from app.db.session import get_session_factory
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from tests.identity.fakes import FakeIdentityProvider

OWNER_TOKEN = "notifications-owner"
OTHER_TOKEN = "notifications-other"


class NotificationsIdentityProvider(FakeIdentityProvider):
    """Maps a fixed set of synthetic bearer tokens to distinct subjects."""

    SUBJECTS_BY_TOKEN: ClassVar[dict[str, str]] = {
        OWNER_TOKEN: "subject-notifications-owner",
        OTHER_TOKEN: "subject-notifications-other",
    }

    def verify_access_token(self, token: str) -> str:
        try:
            return self.SUBJECTS_BY_TOKEN[token]
        except KeyError:
            raise InvalidAccessTokenError from None


@pytest.fixture
def notifications_client(
    application: FastAPI, client: TestClient
) -> Iterator[TestClient]:
    provider = NotificationsIdentityProvider()
    application.dependency_overrides[get_identity_provider] = lambda: provider
    yield client
    application.dependency_overrides.clear()


def authorization(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@dataclass(frozen=True, slots=True)
class NotificationsScenario:
    owner_id: UUID
    other_id: UUID
    owner_newest_unread_id: UUID
    owner_middle_read_id: UUID
    owner_oldest_unread_id: UUID
    other_unread_id: UUID


@pytest.fixture
def scenario() -> Iterator[NotificationsScenario]:
    now = datetime.now(UTC)
    factory = get_session_factory()

    with factory.begin() as session:
        # The owner is a candidate and the other user a company: notifications
        # are available to every account type.
        owner = AppUser(
            email="notifications-owner@synthetic.example.invalid",
            identity_subject=NotificationsIdentityProvider.SUBJECTS_BY_TOKEN[
                OWNER_TOKEN
            ],
            user_type=UserType.CANDIDATE,
        )
        other = AppUser(
            email="notifications-other@synthetic.example.invalid",
            identity_subject=NotificationsIdentityProvider.SUBJECTS_BY_TOKEN[
                OTHER_TOKEN
            ],
            user_type=UserType.COMPANY,
        )
        session.add_all([owner, other])
        session.flush()

        def make(
            user_id: UUID, *, message: str, read: bool, age: timedelta
        ) -> Notification:
            return Notification(
                user_id=user_id,
                type="company_registration_rejected",
                message=message,
                read=read,
                details={"reference_id": "synthetic"},
                created_at=now - age,
            )

        owner_newest_unread = make(
            owner.id, message="Newest", read=False, age=timedelta(minutes=1)
        )
        owner_middle_read = make(
            owner.id, message="Middle", read=True, age=timedelta(hours=1)
        )
        owner_oldest_unread = make(
            owner.id, message="Oldest", read=False, age=timedelta(days=1)
        )
        other_unread = make(
            other.id, message="Other", read=False, age=timedelta(minutes=5)
        )
        session.add_all(
            [owner_newest_unread, owner_middle_read, owner_oldest_unread, other_unread]
        )
        session.flush()

        result = NotificationsScenario(
            owner_id=owner.id,
            other_id=other.id,
            owner_newest_unread_id=owner_newest_unread.id,
            owner_middle_read_id=owner_middle_read.id,
            owner_oldest_unread_id=owner_oldest_unread.id,
            other_unread_id=other_unread.id,
        )

    yield result

    # Notifications are removed by the ON DELETE CASCADE foreign key.
    with factory.begin() as session:
        session.execute(
            delete(AppUser).where(AppUser.id.in_([result.owner_id, result.other_id]))
        )
