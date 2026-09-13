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


@pytest.mark.parametrize(
    "raw_value",
    ["person@gmail.com", "person@mail.gmail.com", "person@a.b.gmail.com"],
)
def test_corporate_email_blocks_personal_subdomains(raw_value: str) -> None:
    with pytest.raises(PersonalEmailDomainError):
        CorporateEmail(raw_value, frozenset({"gmail.com"}))


def test_corporate_email_allows_a_domain_that_only_ends_alike() -> None:
    assert (
        CorporateEmail("sales@notgmail.com", frozenset({"gmail.com"})).value
        == "sales@notgmail.com"
    )
