from typing import Protocol

from app.identity.authenticated_identity import AuthenticatedIdentity
from app.identity.registered_identity import RegisteredIdentity


class IdentityProvider(Protocol):
    def register(self, *, email: str, password: str) -> RegisteredIdentity: ...

    def authenticate(self, *, email: str, password: str) -> AuthenticatedIdentity: ...

    def verify_access_token(self, token: str) -> str:
        """Return the subject only after verifying the token and its intended use."""
        ...

    def confirm_email(self, *, email: str, code: str) -> None: ...

    def resend_confirmation(self, *, email: str) -> None: ...
