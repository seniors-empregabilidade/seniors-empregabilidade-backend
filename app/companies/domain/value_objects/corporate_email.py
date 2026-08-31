from dataclasses import dataclass

from app.companies.domain.exceptions import PersonalEmailDomainError


@dataclass(frozen=True, slots=True)
class CorporateEmail:
    value: str

    def __init__(self, raw_value: str, personal_domains: frozenset[str]) -> None:
        local, separator, domain = raw_value.strip().lower().rpartition("@")
        normalized_domain = domain
        if not separator or not local or normalized_domain in personal_domains:
            raise PersonalEmailDomainError
        object.__setattr__(self, "value", f"{local}@{normalized_domain}")
