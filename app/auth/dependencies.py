from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.schemas.current_user import CurrentUser
from app.auth.services.current_user import find_current_user
from app.core.errors import ProblemException
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session
from app.identity.dependencies import get_identity_provider
from app.identity.exceptions import InvalidAccessTokenError
from app.identity.provider import IdentityProvider

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    provider: Annotated[IdentityProvider, Depends(get_identity_provider)],
    session: Annotated[Session, Depends(get_session)],
) -> CurrentUser:
    if credentials is None:
        raise InvalidAccessTokenError
    subject = provider.verify_access_token(credentials.credentials)
    return find_current_user(session, subject)


def require_candidate(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.user_type != UserType.CANDIDATE:
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            code="candidate_required",
            detail="A candidate account is required.",
        )
    return user


def require_administrator(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.user_type != UserType.ADMINISTRATOR:
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            code="administrator_required",
            detail="An administrator account is required.",
        )
    return user


def require_approved_company(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if (
        user.user_type != UserType.COMPANY
        or user.company_status != CompanyStatus.APPROVED
    ):
        raise ProblemException(
            status_code=403,
            title="Forbidden",
            code="approved_company_required",
            detail="An approved company account is required.",
        )
    return user
