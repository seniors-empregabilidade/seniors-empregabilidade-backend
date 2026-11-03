"""Service checks the HTTP dependency cannot reach.

`require_approved_company` already rejects a blocked company when the request
starts. These tests cover a block committed after that check: the service
re-reads the company under a lock and refuses to write anything.
"""

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.contacts.exceptions import CompanyUnavailableError
from app.contacts.services.contact_professional import contact_professional
from app.db.models import AppUser, Company, ContactRequest, Notification
from app.db.models.enums import AccountStatus, CompanyStatus
from tests.contacts.conftest import ContactsScenario

pytestmark = pytest.mark.integration


def send(session: Session, scenario: ContactsScenario) -> None:
    contact_professional(
        session,
        company_id=scenario.owner_company_id,
        sent_by_user_id=scenario.owner_company_id,
        job_id=scenario.job_id,
        candidate_id=scenario.applicant_id,
        message="Synthetic message.",
    )


def assert_nothing_written(session: Session, scenario: ContactsScenario) -> None:
    assert session.scalar(select(func.count()).select_from(ContactRequest)) == 0
    assert (
        session.scalar(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == scenario.applicant_id)
        )
        == 0
    )


def test_company_account_blocked_meanwhile_cannot_contact(
    database_session: Session, contacts_scenario: ContactsScenario
) -> None:
    database_session.execute(
        update(AppUser)
        .where(AppUser.id == contacts_scenario.owner_company_id)
        .values(account_status=AccountStatus.BLOCKED)
    )
    database_session.commit()

    with pytest.raises(CompanyUnavailableError):
        send(database_session, contacts_scenario)

    assert_nothing_written(database_session, contacts_scenario)


def test_company_registration_blocked_meanwhile_cannot_contact(
    database_session: Session, contacts_scenario: ContactsScenario
) -> None:
    database_session.execute(
        update(Company)
        .where(Company.id == contacts_scenario.owner_company_id)
        .values(status=CompanyStatus.BLOCKED)
    )
    database_session.commit()

    with pytest.raises(CompanyUnavailableError):
        send(database_session, contacts_scenario)

    assert_nothing_written(database_session, contacts_scenario)


def test_company_falls_back_to_its_legal_name(
    database_session: Session, contacts_scenario: ContactsScenario
) -> None:
    database_session.execute(
        update(Company)
        .where(Company.id == contacts_scenario.owner_company_id)
        .values(trade_name=None)
    )
    database_session.commit()

    send(database_session, contacts_scenario)

    message = database_session.scalars(
        select(Notification.message).where(
            Notification.user_id == contacts_scenario.applicant_id
        )
    ).one()
    assert message.startswith("Contacts Owner Legal Name entrou em contato")
