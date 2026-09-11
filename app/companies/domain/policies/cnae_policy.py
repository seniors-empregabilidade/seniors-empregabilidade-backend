from app.companies.domain.exceptions import CompanySegmentBlockedError


def ensure_cnae_is_allowed(cnae: str, blocked_prefixes: tuple[str, ...]) -> None:
    normalized = "".join(character for character in cnae if character.isdigit())
    if any(normalized.startswith(prefix) for prefix in blocked_prefixes):
        raise CompanySegmentBlockedError
