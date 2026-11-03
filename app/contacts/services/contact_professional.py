from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contacts.domain.contact_message import contact_message
from app.contacts.exceptions import (
    CompanyUnavailableError,
    ProfessionalNotFoundError,
    ProfessionalUnavailableError,
)
from app.db.models import AppUser, Company, ContactRequest, Job
from app.db.models.enums import AccountStatus, CompanyStatus, EmailDeliveryStatus
from app.jobs.services.list_job_applicants import list_job_applicants
from app.notifications.domain.notification_type import NotificationType
from app.notifications.services.notify_user import notify_user


@dataclass(frozen=True, slots=True)
class SentContact:
    id: UUID
    job_id: UUID
    candidate_id: UUID
    created_at: datetime
    email_status: EmailDeliveryStatus


def contact_professional(
    session: Session,
    *,
    company_id: UUID,
    sent_by_user_id: UUID,
    job_id: UUID,
    candidate_id: UUID,
    message: str,
) -> SentContact:
    """Send a company's message to a professional listed for one of its jobs.

    The professional must appear in the job's list (an applicant or an automatic
    match, US-19/US-20), so a company can only reach people it was shown, and
    only about its own job. Blocked or suspended accounts, on either side,
    cannot take part (US-12).

    Both accounts are locked with `FOR SHARE` before their status is read, so
    an administrator's block that commits first is the status seen here, and a
    block issued meanwhile waits for this contact to finish.

    The professional is told through `notify_user` (US-26): the in-app
    notification, its queued e-mail and the contact record commit together. The
    e-mail is sent later by the dispatcher to the address on the professional's
    account, which the company never sees; a failed e-mail leaves the
    notification and the record untouched, and its result is kept in
    `email_delivery`.
    """
    try:
        company_name = _lock_available_company(session, company_id=company_id)
        listed = list_job_applicants(session, job_id=job_id, company_id=company_id)
        if candidate_id not in {
            applicant.profile.candidate_id for applicant in listed.applicants
        }:
            raise ProfessionalNotFoundError
        _lock_available_professional(session, candidate_id=candidate_id)

        job_title = session.scalars(select(Job.title).where(Job.id == job_id)).one()
        notification = notify_user(
            session,
            user_id=candidate_id,
            type=NotificationType.CONTACT_RECEIVED,
            message=contact_message(
                company_name=company_name, job_title=job_title, message=message
            ),
        )
        contact = ContactRequest(
            company_id=company_id,
            sent_by_user_id=sent_by_user_id,
            candidate_id=candidate_id,
            job_id=job_id,
            message=message,
            notification=notification,
        )
        session.add(contact)
        session.flush()
        # Only identifiers go to the professional: the company and the job are
        # already named in the message.
        notification.details = {"contact_id": str(contact.id), "job_id": str(job_id)}
        sent = SentContact(
            id=contact.id,
            job_id=contact.job_id,
            candidate_id=contact.candidate_id,
            created_at=contact.created_at,
            # The e-mail was only queued; the dispatcher sends it after commit.
            email_status=EmailDeliveryStatus.PENDING,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return sent


def _lock_available_company(session: Session, *, company_id: UUID) -> str:
    """Lock the company account and return the name shown to the professional."""
    company = session.execute(
        select(
            AppUser.account_status,
            Company.status,
            Company.trade_name,
            Company.legal_name,
        )
        .join(Company, Company.id == AppUser.id)
        .where(AppUser.id == company_id)
        .with_for_update(read=True, of=AppUser)
    ).one_or_none()
    if (
        company is None
        or company.account_status != AccountStatus.ACTIVE
        or company.status != CompanyStatus.APPROVED
    ):
        raise CompanyUnavailableError
    return str(company.trade_name or company.legal_name)


def _lock_available_professional(session: Session, *, candidate_id: UUID) -> None:
    account_status = session.scalar(
        select(AppUser.account_status)
        .where(AppUser.id == candidate_id)
        .with_for_update(read=True)
    )
    if account_status != AccountStatus.ACTIVE:
        raise ProfessionalUnavailableError
