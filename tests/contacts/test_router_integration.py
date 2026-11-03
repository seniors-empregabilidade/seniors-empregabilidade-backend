"""Integration tests for POST /api/v1/contacts (US-29-T01)."""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.db.models import (
    AppUser,
    Company,
    ContactRequest,
    EmailDelivery,
    EmailDeliveryStatus,
    Notification,
)
from app.db.models.enums import AccountStatus, CompanyStatus
from app.email.email_sender import EmailSendError
from app.notifications.services.dispatch_pending_emails import (
    dispatch_pending_emails,
)
from tests.contacts.conftest import (
    APPLICANT_CPF,
    APPLICANT_EMAIL,
    APPLICANT_NAME,
    APPLICANT_PHONE,
    CANDIDATE_TOKEN,
    COMPANY_TRADE_NAME,
    JOB_TITLE,
    OTHER_COMPANY_TOKEN,
    OWNER_TOKEN,
    ContactsScenario,
    authorization,
)

pytestmark = pytest.mark.integration

CONTACTS_PATH = "/api/v1/contacts"
APP_URL = "https://app.example.invalid"
MESSAGE = "Gostaríamos de conversar sobre a vaga. Responda pelo RH."


class FakeEmailSender:
    def __init__(self, failure_code: str | None = None) -> None:
        self.failure_code = failure_code
        self.sent: list[tuple[str, str, str]] = []

    def send(self, *, to: str, subject: str, body: str) -> None:
        if self.failure_code is not None:
            raise EmailSendError(self.failure_code)
        self.sent.append((to, subject, body))


def contact(
    client: TestClient,
    *,
    job_id: UUID,
    candidate_id: UUID,
    message: str = MESSAGE,
    token: str = OWNER_TOKEN,
) -> Any:
    return client.post(
        CONTACTS_PATH,
        json={
            "job_id": str(job_id),
            "candidate_id": str(candidate_id),
            "message": message,
        },
        headers=authorization(token),
    )


def contact_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ContactRequest)) or 0


def notifications_of(session: Session, user_id: UUID) -> list[Notification]:
    return list(
        session.scalars(select(Notification).where(Notification.user_id == user_id))
    )


def dispatch(session: Session, sender: FakeEmailSender) -> int:
    return dispatch_pending_emails(
        session,
        sender=sender,
        app_url=APP_URL,
        max_attempts=5,
        now=datetime.now(UTC) + timedelta(minutes=1),
    )


def test_company_contacts_an_applicant_and_the_contact_is_recorded(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    assert response.status_code == 201
    assert response.headers["Cache-Control"] == "no-store"
    body = response.json()
    assert set(body) == {"id", "job_id", "candidate_id", "created_at", "email_status"}
    assert body["job_id"] == str(contacts_scenario.job_id)
    assert body["candidate_id"] == str(contacts_scenario.applicant_id)
    assert body["email_status"] == "pending"

    record = database_session.get(ContactRequest, UUID(body["id"]))
    assert record is not None
    assert record.company_id == contacts_scenario.owner_company_id
    assert record.sent_by_user_id == contacts_scenario.owner_company_id
    assert record.candidate_id == contacts_scenario.applicant_id
    assert record.job_id == contacts_scenario.job_id
    assert record.message == MESSAGE
    assert record.created_at is not None


def test_response_never_exposes_the_professionals_personal_data(
    contacts_client: TestClient, contacts_scenario: ContactsScenario
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    for personal in (APPLICANT_EMAIL, APPLICANT_CPF, APPLICANT_PHONE, APPLICANT_NAME):
        assert personal not in response.text


def test_professional_is_notified_inside_the_platform(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    [notification] = notifications_of(database_session, contacts_scenario.applicant_id)
    assert notification.type == "contact_received"
    assert COMPANY_TRADE_NAME in notification.message
    assert JOB_TITLE in notification.message
    assert MESSAGE in notification.message
    assert notification.details == {
        "contact_id": response.json()["id"],
        "job_id": str(contacts_scenario.job_id),
    }


def test_message_is_stripped_before_it_is_recorded(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
        message=f"  {MESSAGE}\n",
    )

    record = database_session.get(ContactRequest, UUID(response.json()["id"]))
    assert record is not None
    assert record.message == MESSAGE


def test_automatic_match_can_be_contacted(
    contacts_client: TestClient, contacts_scenario: ContactsScenario
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.automatic_match_id,
    )

    assert response.status_code == 201


def test_same_professional_can_be_contacted_again(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    for _ in range(2):
        response = contact(
            contacts_client,
            job_id=contacts_scenario.job_id,
            candidate_id=contacts_scenario.applicant_id,
        )
        assert response.status_code == 201

    assert contact_count(database_session) == 2
    assert len(notifications_of(database_session, contacts_scenario.applicant_id)) == 2


def test_professional_outside_the_job_list_is_not_found(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.unlisted_id,
    )

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "professional_not_found"
    assert contact_count(database_session) == 0
    assert notifications_of(database_session, contacts_scenario.unlisted_id) == []


def test_unknown_professional_is_not_found(
    contacts_client: TestClient, contacts_scenario: ContactsScenario
) -> None:
    response = contact(
        contacts_client, job_id=contacts_scenario.job_id, candidate_id=uuid4()
    )

    assert response.status_code == 404
    assert response.json()["code"] == "professional_not_found"


@pytest.mark.parametrize("job", ["other_company", "unknown"])
def test_job_of_another_company_is_not_found(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
    job: str,
) -> None:
    job_id = (
        contacts_scenario.other_company_job_id if job == "other_company" else uuid4()
    )

    response = contact(
        contacts_client, job_id=job_id, candidate_id=contacts_scenario.applicant_id
    )

    assert response.status_code == 404
    assert response.json()["code"] == "job_not_found"
    assert contact_count(database_session) == 0


def test_blocked_professional_cannot_be_contacted(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.blocked_applicant_id,
    )

    assert response.status_code == 409
    assert response.json()["code"] == "professional_unavailable"
    assert contact_count(database_session) == 0
    assert (
        notifications_of(database_session, contacts_scenario.blocked_applicant_id) == []
    )


def test_blocked_company_cannot_contact(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    database_session.execute(
        update(AppUser)
        .where(AppUser.id == contacts_scenario.owner_company_id)
        .values(account_status=AccountStatus.BLOCKED)
    )
    database_session.commit()

    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "account_unavailable"
    assert contact_count(database_session) == 0


def test_company_blocked_in_its_registration_cannot_contact(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    database_session.execute(
        update(Company)
        .where(Company.id == contacts_scenario.owner_company_id)
        .values(status=CompanyStatus.BLOCKED)
    )
    database_session.commit()

    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "approved_company_required"
    assert contact_count(database_session) == 0


def test_candidate_cannot_send_a_contact(
    contacts_client: TestClient, contacts_scenario: ContactsScenario
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
        token=CANDIDATE_TOKEN,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "approved_company_required"


def test_missing_token_is_rejected(contacts_client: TestClient) -> None:
    response = contacts_client.post(
        CONTACTS_PATH,
        json={"job_id": str(uuid4()), "candidate_id": str(uuid4()), "message": "Hi"},
    )

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_access_token"


@pytest.mark.parametrize(
    "payload_change",
    [
        {"message": "   "},
        {"message": "x" * 2001},
        {"message": None},
        {"candidate_id": "not-a-uuid"},
        {"email": "company@example.invalid"},
    ],
)
def test_invalid_body_is_rejected_without_writing(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
    payload_change: dict[str, object],
) -> None:
    payload: dict[str, object] = {
        "job_id": str(contacts_scenario.job_id),
        "candidate_id": str(contacts_scenario.applicant_id),
        "message": MESSAGE,
        **payload_change,
    }

    response = contacts_client.post(
        CONTACTS_PATH, json=payload, headers=authorization(OTHER_COMPANY_TOKEN)
    )

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert contact_count(database_session) == 0


def test_email_reaches_the_professional_without_personal_data(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )
    sender = FakeEmailSender()

    assert dispatch(database_session, sender) == 1

    [(to, subject, body)] = sender.sent
    assert to == APPLICANT_EMAIL
    assert subject == "Uma empresa entrou em contato com você"
    assert COMPANY_TRADE_NAME in body
    assert JOB_TITLE in body
    assert MESSAGE in body
    assert APP_URL in body
    for personal in (APPLICANT_CPF, APPLICANT_PHONE, APPLICANT_NAME):
        assert personal not in body


def test_email_result_is_kept_with_the_contact(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    dispatch(database_session, FakeEmailSender())

    status = database_session.scalar(
        select(EmailDelivery.status)
        .join(
            ContactRequest,
            ContactRequest.notification_id == EmailDelivery.notification_id,
        )
        .where(ContactRequest.id == UUID(response.json()["id"]))
    )
    assert status == EmailDeliveryStatus.SENT


def test_email_failure_keeps_the_notification_and_the_record(
    contacts_client: TestClient,
    database_session: Session,
    contacts_scenario: ContactsScenario,
) -> None:
    response = contact(
        contacts_client,
        job_id=contacts_scenario.job_id,
        candidate_id=contacts_scenario.applicant_id,
    )

    dispatch(database_session, FakeEmailSender(failure_code="MessageRejected"))

    record = database_session.get(ContactRequest, UUID(response.json()["id"]))
    assert record is not None
    delivery = database_session.scalars(
        select(EmailDelivery).where(
            EmailDelivery.notification_id == record.notification_id
        )
    ).one()
    assert delivery.status == EmailDeliveryStatus.PENDING
    assert delivery.last_error == "MessageRejected"
    [notification] = notifications_of(database_session, contacts_scenario.applicant_id)
    assert notification.id == record.notification_id
    assert notification.read is False
