import logging

_logger = logging.getLogger("app.email")


class LogEmailSender:
    """Accepts every message and only records that one was produced.

    Used locally and in tests. The recipient and the content are personal data,
    so neither is logged.
    """

    def send(self, *, to: str, subject: str, body: str) -> None:
        _logger.info("email_logged", extra={"event": "email_logged"})
