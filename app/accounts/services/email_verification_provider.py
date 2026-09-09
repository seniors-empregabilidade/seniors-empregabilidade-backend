from typing import Protocol


class EmailVerificationProvider(Protocol):
    """Sends and confirms email verification codes through an external provider.

    The provider owns the code: it generates it, delivers the message, decides
    when it expires, and validates it. This application stores only the outcome,
    so a code never reaches the database or the logs.

    Implementations raise the typed failures in `app.accounts.exceptions` and never
    surface provider messages, payloads, or the code itself to the caller.
    """

    def send_code(self, *, email: str) -> None:
        """Deliver a fresh verification code to the address.

        Succeeds silently when the address cannot receive one, so that a caller
        cannot use this operation to discover which emails are registered.
        """
        ...

    def confirm_code(self, *, email: str, code: str) -> None:
        """Validate a code for the address.

        Returns normally when the code is accepted. Raises
        `InvalidVerificationCodeError` when it does not match and
        `VerificationCodeExpiredError` when it is past its validity window.
        """
        ...
