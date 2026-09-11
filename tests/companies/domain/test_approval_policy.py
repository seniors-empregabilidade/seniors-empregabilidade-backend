from typing import Literal

import pytest

from app.companies.domain.exceptions import InvalidCompanyDecisionError
from app.companies.domain.policies.approval_policy import (
    ensure_decision_reason_is_valid,
)


@pytest.mark.parametrize("reason", [None, "", " "])
def test_rejection_requires_a_reason(reason: str | None) -> None:
    with pytest.raises(InvalidCompanyDecisionError):
        ensure_decision_reason_is_valid("rejected", reason)


def test_approval_rejects_an_unrelated_reason() -> None:
    with pytest.raises(InvalidCompanyDecisionError):
        ensure_decision_reason_is_valid("approved", "Synthetic reason")


@pytest.mark.parametrize(
    "status,reason", [("approved", None), ("rejected", "Synthetic reason")]
)
def test_valid_decisions_are_allowed(
    status: Literal["approved", "rejected"], reason: str | None
) -> None:
    ensure_decision_reason_is_valid(status, reason)
