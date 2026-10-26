from dataclasses import dataclass
from typing import Any, Literal

from app.db.models.enums import AccountStatus, CompanyStatus, UserType


@dataclass(frozen=True, slots=True)
class AccountFilters:
    """Filters shared by the account listing and its CSV export."""

    user_type: UserType | None = None
    account_status: AccountStatus | None = None
    company_status: CompanyStatus | None = None
    min_completion: int | None = None
    max_completion: int | None = None
    completeness: Literal["complete", "incomplete"] | None = None

    def applied(self) -> dict[str, Any]:
        """The filters actually sent, as JSON values for the audit log."""
        values: dict[str, Any] = {
            "user_type": self.user_type.value if self.user_type else None,
            "account_status": self.account_status.value
            if self.account_status
            else None,
            "company_status": self.company_status.value
            if self.company_status
            else None,
            "min_completion": self.min_completion,
            "max_completion": self.max_completion,
            "completeness": self.completeness,
        }
        return {name: value for name, value in values.items() if value is not None}
