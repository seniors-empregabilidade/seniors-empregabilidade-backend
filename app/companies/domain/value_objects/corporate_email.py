from dataclasses import dataclass

from app.companies.domain.exceptions import PersonalEmailDomainError


@dataclass(frozen=True, slots=True)
class CorporateEmail:
    value: str

    def __init__(self, raw_value: str, personal_domains: frozenset[str]) -> None:
        local, separator, domain = raw_value.strip().lower().rpartition("@")
        normalized_domain = domain
        if (
            not separator
            or not local
            or _matches_personal(normalized_domain, personal_domains)
        ):
            raise PersonalEmailDomainError
        object.__setattr__(self, "value", f"{local}@{normalized_domain}")


def _matches_personal(domain: str, personal_domains: frozenset[str]) -> bool:
    labels = domain.split(".")
    suffixes = {".".join(labels[index:]) for index in range(len(labels))}
    return bool(suffixes & personal_domains)
