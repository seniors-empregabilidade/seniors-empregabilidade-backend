import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, Notification
from app.db.models.enums import UserType
from app.notifications.domain.notification_type import NotificationType
from app.notifications.services.notify_user import notify_user

pytestmark = pytest.mark.integration


def make_user(session: Session) -> AppUser:
    user = AppUser(
        email="notify-user@synthetic.example.invalid",
        identity_subject=None,
        user_type=UserType.CANDIDATE,
    )
    session.add(user)
    session.flush()
    return user


def test_notification_is_created_unread_in_the_callers_transaction(
    database_session: Session,
) -> None:
    user = make_user(database_session)

    notify_user(
        database_session,
        user_id=user.id,
        type=NotificationType.COMPANY_REGISTRATION_REJECTED,
        message="Synthetic message",
        details={"company_id": str(user.id)},
    )
    database_session.flush()

    notification = database_session.scalar(
        select(Notification).where(Notification.user_id == user.id)
    )
    assert notification is not None
    assert notification.type == "company_registration_rejected"
    assert notification.message == "Synthetic message"
    assert notification.details == {"company_id": str(user.id)}
    assert notification.read is False
    assert notification.created_at is not None


def test_notification_is_discarded_when_the_caller_rolls_back(
    database_session: Session,
) -> None:
    user = make_user(database_session)
    database_session.commit()

    notify_user(
        database_session,
        user_id=user.id,
        type=NotificationType.COMPANY_REGISTRATION_REJECTED,
        message="Synthetic message",
    )
    database_session.rollback()

    assert (
        database_session.scalar(
            select(Notification).where(Notification.user_id == user.id)
        )
        is None
    )
