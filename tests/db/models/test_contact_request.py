from app.db.models import ContactRequest
from tests.db.models.assertions import (
    foreign_key_for,
    has_check_constraint,
    has_index,
    has_unique_constraint,
    table_for,
)


def test_record_keeps_company_professional_and_job() -> None:
    for column, target in (
        ("company_id", "company.id"),
        ("candidate_id", "candidate.id"),
        ("job_id", "job.id"),
        ("notification_id", "notification.id"),
    ):
        foreign_key = foreign_key_for(ContactRequest, column)
        assert foreign_key.ondelete == "CASCADE"
        assert foreign_key.elements[0].target_fullname == target


def test_sender_survives_as_null_when_the_account_is_deleted() -> None:
    sender = foreign_key_for(ContactRequest, "sent_by_user_id")

    assert sender.ondelete == "SET NULL"
    assert table_for(ContactRequest).c.sent_by_user_id.nullable is True


def test_each_notification_belongs_to_one_contact() -> None:
    assert has_unique_constraint(ContactRequest, ["notification_id"])


def test_message_length_is_constrained() -> None:
    assert has_check_constraint(ContactRequest, "ck_contact_request_message_length")


def test_company_contacts_are_indexed_newest_first() -> None:
    assert has_index(ContactRequest, "ix_contact_request_company_id_created_at")


def test_record_stores_no_address_of_the_professional() -> None:
    assert not {"email", "recipient", "phone", "address", "cpf"} & set(
        table_for(ContactRequest).c.keys()
    )
