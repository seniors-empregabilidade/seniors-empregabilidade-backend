from dataclasses import dataclass

from app.identity.tokens import IdentityTokens


@dataclass(frozen=True, slots=True)
class AuthenticatedIdentity:
    identity_subject: str
    tokens: IdentityTokens
