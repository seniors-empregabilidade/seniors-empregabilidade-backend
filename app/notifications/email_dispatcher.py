import logging
import threading
from collections.abc import Callable

from app.core.config import Settings
from app.db.session import get_session_factory
from app.email.dependencies import build_email_sender
from app.notifications.services.dispatch_pending_emails import (
    dispatch_pending_emails,
)

_logger = logging.getLogger("app.email")


class EmailDispatcher:
    """Runs `run_once` every `interval_seconds` on a daemon thread.

    The API runs a single worker, so one in-process loop is enough; the
    `SKIP LOCKED` claim in `dispatch_pending_emails` keeps a second process
    safe anyway. A failing round is logged and retried on the next tick.
    """

    def __init__(self, run_once: Callable[[], object], interval_seconds: float):
        self._run_once = run_once
        self._interval_seconds = interval_seconds
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, name="email-dispatcher", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval_seconds + 5)

    def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                self._run_once()
            except Exception as exc:
                _logger.error(
                    "email_dispatch_round_failed",
                    extra={
                        "event": "email_dispatch_round_failed",
                        "exception_type": type(exc).__name__,
                    },
                )
            self._stopped.wait(self._interval_seconds)


def build_email_dispatcher(settings: Settings) -> EmailDispatcher:
    sender = build_email_sender(settings)

    def run_once() -> int:
        with get_session_factory()() as session:
            return dispatch_pending_emails(
                session,
                sender=sender,
                app_url=settings.app_public_url_value,
                max_attempts=settings.email_max_attempts,
            )

    return EmailDispatcher(run_once, settings.email_dispatch_interval_seconds)
