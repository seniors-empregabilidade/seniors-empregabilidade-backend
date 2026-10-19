from app.db.models import EmailDelivery
from app.db.models.enums import EmailDeliveryStatus
from tests.db.models.assertions import (
    foreign_key_for,
    has_index,
    has_unique_constraint,
    table_for,
)


def test_notification_foreign_key_cascades() -> None:
    notification_fk = foreign_key_for(EmailDelivery, "notification_id")

    assert notification_fk.ondelete == "CASCADE"
    assert notification_fk.deferrable is True


def test_each_notification_has_at_most_one_delivery() -> None:
    assert has_unique_constraint(EmailDelivery, ["notification_id"])


def test_due_deliveries_are_indexed_by_status_and_time() -> None:
    assert has_index(EmailDelivery, "ix_email_delivery_status_next_attempt_at")


def test_delivery_starts_pending_without_attempts() -> None:
    columns = EmailDelivery.__table__.c

    assert str(columns.status.server_default.arg) == EmailDeliveryStatus.PENDING.value
    assert str(columns.attempts.server_default.arg) == "0"


def test_delivery_stores_no_recipient_address() -> None:
    assert not {"email", "recipient", "to"} & set(table_for(EmailDelivery).c.keys())
