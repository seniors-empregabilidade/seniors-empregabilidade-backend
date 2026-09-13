from typing import Any
from uuid import uuid4

import pytest

from app.companies.schemas.company_approval import CompanyApprovalRequest
from app.companies.services.review_company import review_company
from app.core.errors import ProblemException
from app.db.models import Company
from app.db.models.enums import CompanyStatus


class SessionWithoutOwner:
    def __init__(self, company: Company) -> None:
        self.company = company
        self.rolled_back = False
        self.committed = False

    def scalar(self, *args: Any, **kwargs: Any) -> Company:
        return self.company

    def get(self, *args: Any, **kwargs: Any) -> None:
        return None

    def add(self, *args: Any, **kwargs: Any) -> None:
        return None

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


def test_missing_owner_is_reported_instead_of_asserted() -> None:
    company = Company(
        id=uuid4(), primary_cnae="62.01-5-01", status=CompanyStatus.PENDING
    )
    session = SessionWithoutOwner(company)

    with pytest.raises(ProblemException) as error:
        review_company(
            company.id,
            CompanyApprovalRequest(status="approved", reason=None),
            session=session,  # type: ignore[arg-type]
            blocked_cnae_prefixes=(),
        )

    assert error.value.status_code == 404
    assert error.value.code == "company_not_found"
    assert session.rolled_back
    assert not session.committed
