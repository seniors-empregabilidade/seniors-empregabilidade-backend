import logging
import threading
from collections.abc import Callable

from app.applications.services.generate_automatic_applications import (
    generate_automatic_applications_for_new_candidates,
)
from app.core.config import Settings
from app.db.session import get_session_factory

_logger = logging.getLogger("app.applications")


class AutomaticApplicationScheduler:
    """Runs `run_once` on start and then every `interval_seconds` on a daemon thread.

    The API runs a single worker, so one in-process loop is enough. Running again
    after a restart is harmless: a professional who already has an application to a
    job is never given a second one. A failing round is logged and retried on the
    next tick.
    """

    def __init__(self, run_once: Callable[[], object], interval_seconds: float):
        self._run_once = run_once
        self._interval_seconds = interval_seconds
        self._stopped = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._loop, name="automatic-applications", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stopped.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stopped.is_set():
            try:
                self._run_once()
            except Exception as exc:
                _logger.error(
                    "automatic_applications_failed",
                    extra={
                        "event": "automatic_applications_failed",
                        "trigger": "daily",
                        "exception_type": type(exc).__name__,
                    },
                )
            self._stopped.wait(self._interval_seconds)


def build_automatic_application_scheduler(
    settings: Settings,
) -> AutomaticApplicationScheduler:
    def run_once() -> int:
        with get_session_factory()() as session:
            return generate_automatic_applications_for_new_candidates(
                session,
                threshold_percent=settings.automatic_application_threshold_percent,
            )

    return AutomaticApplicationScheduler(
        run_once, settings.automatic_application_interval_seconds
    )
