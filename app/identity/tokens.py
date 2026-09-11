from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class IdentityTokens:
    access_token: str = field(repr=False)
    id_token: str = field(repr=False)
    refresh_token: str | None = field(repr=False)
    expires_in: int
    token_type: str
