from uuid import UUID

from pydantic import BaseModel

from app.db.models.enums import AccountStatus


class AccountStatusResponse(BaseModel):
    id: UUID
    account_status: AccountStatus
