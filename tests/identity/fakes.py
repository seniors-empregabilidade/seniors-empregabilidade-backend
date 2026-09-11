from app.identity.authenticated_identity import AuthenticatedIdentity
from app.identity.registered_identity import RegisteredIdentity
from app.identity.tokens import IdentityTokens


class FakeIdentityProvider:
    def __init__(self) -> None:
        self.subject = "synthetic-subject"
        self.confirmed = False
        self.error: Exception | None = None
        self.calls: list[str] = []

    def _call(self, operation: str) -> None:
        self.calls.append(operation)
        if self.error:
            raise self.error

    def register(self, *, email: str, password: str) -> RegisteredIdentity:
        self._call("register")
        return RegisteredIdentity(self.subject, self.confirmed)

    def authenticate(self, *, email: str, password: str) -> AuthenticatedIdentity:
        self._call("authenticate")
        return AuthenticatedIdentity(
            self.subject, IdentityTokens("access", "id", "refresh", 900, "Bearer")
        )

    def verify_access_token(self, token: str) -> str:
        self._call("verify")
        return self.subject

    def confirm_email(self, *, email: str, code: str) -> None:
        self._call("confirm")
        self.confirmed = True

    def resend_confirmation(self, *, email: str) -> None:
        self._call("resend")
