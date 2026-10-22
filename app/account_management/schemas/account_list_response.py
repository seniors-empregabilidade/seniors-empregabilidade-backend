from pydantic import BaseModel, Field

from app.account_management.schemas.account_summary_response import (
    AccountSummaryResponse,
)


class AccountListResponse(BaseModel):
    items: list[AccountSummaryResponse]
    total: int = Field(description="Every account matching the filters.")
