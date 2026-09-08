from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class IdentityTokens:
    """Tokens issued by the identity provider, parsed into an owned value.

    Provider payloads stop at the adapter; only this value crosses into the
    application operation.
    """

    access_token: str
    id_token: str
    refresh_token: str | None
    expires_in: int
    token_type: str


class IdentityProvider(Protocol):
    """Verifies credentials against the external identity provider.

    Implementations raise the typed failures in `app.auth.exceptions` and never
    surface provider messages, payloads, or challenge sessions to the caller.
    """

    def authenticate(self, *, email: str, password: str) -> IdentityTokens: ...
