import pytest

from app.companies.domain.exceptions import (
    CompanySegmentBlockedError,
    PersonalEmailDomainError,
)
from app.companies.domain.policies.cnae_policy import ensure_cnae_is_allowed
from app.companies.domain.value_objects.corporate_email import CorporateEmail


def test_cnae_policy_blocks_configured_prefix() -> None:
    with pytest.raises(CompanySegmentBlockedError):
        ensure_cnae_is_allowed("94.30-8-00", ("943",))


def test_corporate_email_normalizes_domain_and_blocks_personal_domain() -> None:
    assert (
        CorporateEmail("Sales@Example.Invalid", frozenset()).value
        == "sales@example.invalid"
    )
    with pytest.raises(PersonalEmailDomainError):
        CorporateEmail("person@gmail.com", frozenset({"gmail.com"}))
