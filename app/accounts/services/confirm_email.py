from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.accounts.schemas.email_confirmation import EmailConfirmationRequest
from app.db.models import AppUser, Company
from app.identity.provider import IdentityProvider


def confirm_account_email(
    request: EmailConfirmationRequest, *, provider: IdentityProvider, session: Session
) -> None:
    provider.confirm_email(email=request.email, code=request.code.get_secret_value())
    user_id = select(AppUser.id).where(
        AppUser.email == request.email, AppUser.identity_subject.is_not(None)
    )
    session.execute(
        update(Company)
        .where(Company.id.in_(user_id))
        .values(corporate_email_confirmed=True)
    )
    session.commit()
