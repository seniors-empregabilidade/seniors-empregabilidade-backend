from typing import Literal

from app.companies.domain.exceptions import InvalidCompanyDecisionError


def ensure_decision_reason_is_valid(
    status: Literal["approved", "rejected"], reason: str | None
) -> None:
    if status == "rejected" and (reason is None or not reason.strip()):
        raise InvalidCompanyDecisionError
    if status == "approved" and reason is not None:
        raise InvalidCompanyDecisionError
