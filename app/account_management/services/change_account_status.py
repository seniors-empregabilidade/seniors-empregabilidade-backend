from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.account_management.exceptions import (
    AccountAlreadyActiveError,
    AccountAlreadyBlockedError,
    AccountNotFoundError,
)
from app.account_management.schemas.account_status_request import AccountStatusRequest
from app.account_management.schemas.account_status_response import (
    AccountStatusResponse,
)
from app.account_management.services.list_accounts import MANAGED_USER_TYPES
from app.db.models import AppUser, Event
from app.db.models.enums import AccountStatus

ACCOUNT_BLOCKED_EVENT = "account_blocked"
ACCOUNT_REACTIVATED_EVENT = "account_reactivated"


def change_account_status(
    session: Session,
    *,
    administrator_id: UUID,
    account_id: UUID,
    request: AccountStatusRequest,
) -> AccountStatusResponse:
    try:
        account = session.scalar(
            select(AppUser)
            .where(
                AppUser.id == account_id,
                AppUser.user_type.in_(MANAGED_USER_TYPES),
            )
            .with_for_update()
        )
        if account is None:
            raise AccountNotFoundError
        new_status = AccountStatus(request.status)
        if new_status == account.account_status:
            raise (
                AccountAlreadyBlockedError
                if new_status == AccountStatus.BLOCKED
                else AccountAlreadyActiveError
            )
        previous_status = account.account_status
        account.account_status = new_status
        account.updated_at = datetime.now(UTC)
        session.add(
            Event(
                user_id=administrator_id,
                event_type=(
                    ACCOUNT_BLOCKED_EVENT
                    if new_status == AccountStatus.BLOCKED
                    else ACCOUNT_REACTIVATED_EVENT
                ),
                details={
                    "target_user_id": str(account.id),
                    "previous_status": previous_status.value,
                    "new_status": new_status.value,
                    "reason": request.reason,
                },
            )
        )
        response = AccountStatusResponse(
            id=account.id, account_status=account.account_status
        )
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
