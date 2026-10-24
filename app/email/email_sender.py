from typing import Protocol


class EmailSendError(Exception):
    """The provider did not accept the message.

    `code` is a short provider error code (for example `MessageRejected`) that is
    safe to store and log; it never carries the recipient or the message text.
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class EmailSender(Protocol):
    def send(self, *, to: str, subject: str, body: str) -> None:
        """Send a plain-text message or raise `EmailSendError`."""
        ...
