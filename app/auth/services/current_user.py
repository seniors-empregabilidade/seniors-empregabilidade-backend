from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.schemas.current_user import CurrentUser
from app.core.errors import ProblemException
from app.db.models import AppUser, Company
from app.db.models.enums import AccountStatus
from app.identity.exceptions import InvalidAccessTokenError


def find_current_user(session: Session, identity_subject: str) -> CurrentUser:
    user = session.scalar(
        select(AppUser).where(AppUser.identity_subject == identity_subject)
    )
    if user is None:
        raise InvalidAccessTokenError
    if user.account_status != AccountStatus.ACTIVE:
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            code="account_unavailable",
            detail="This account cannot access the application.",
        )
    company = session.get(Company, user.id)
    return CurrentUser(
        id=user.id,
        user_type=user.user_type,
        company_status=company.status if company else None,
    )
