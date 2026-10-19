import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AppUser, EmailDelivery, EmailDeliveryStatus, Notification
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


def deliveries_for(session: Session, user_id: object) -> list[EmailDelivery]:
    return list(
        session.scalars(
            select(EmailDelivery)
            .join(Notification, Notification.id == EmailDelivery.notification_id)
            .where(Notification.user_id == user_id)
        ).all()
    )


@pytest.mark.parametrize(
    "notification_type",
    [
        NotificationType.APPLICATION_RECEIVED,
        NotificationType.APPLICATION_STATUS_CHANGED,
    ],
)
def test_email_events_queue_one_pending_delivery(
    database_session: Session, notification_type: NotificationType
) -> None:
    user = make_user(database_session)

    notify_user(
        database_session,
        user_id=user.id,
        type=notification_type,
        message="Synthetic message",
    )
    database_session.flush()

    deliveries = deliveries_for(database_session, user.id)
    assert len(deliveries) == 1
    delivery = deliveries[0]
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.attempts == 0
    assert delivery.sent_at is None
    assert delivery.last_error is None


def test_in_app_only_event_queues_no_email(database_session: Session) -> None:
    user = make_user(database_session)

    notify_user(
        database_session,
        user_id=user.id,
        type=NotificationType.COMPANY_REGISTRATION_REJECTED,
        message="Synthetic message",
    )
    database_session.flush()

    assert deliveries_for(database_session, user.id) == []


def test_queued_email_is_discarded_with_its_notification(
    database_session: Session,
) -> None:
    user = make_user(database_session)
    database_session.commit()

    notify_user(
        database_session,
        user_id=user.id,
        type=NotificationType.APPLICATION_RECEIVED,
        message="Synthetic message",
    )
    database_session.rollback()

    assert deliveries_for(database_session, user.id) == []
