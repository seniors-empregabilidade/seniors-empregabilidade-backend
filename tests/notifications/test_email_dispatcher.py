import logging
import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.main as main_module
from app.core.config import Settings
from app.main import create_app
from app.notifications.email_dispatcher import (
    EmailDispatcher,
    build_email_dispatcher,
)


def test_dispatcher_runs_rounds_until_stopped() -> None:
    rounds = threading.Semaphore(0)
    dispatcher = EmailDispatcher(rounds.release, interval_seconds=0.01)

    dispatcher.start()
    assert rounds.acquire(timeout=2)
    assert rounds.acquire(timeout=2)
    dispatcher.stop()

    assert dispatcher._thread is not None
    assert not dispatcher._thread.is_alive()


def test_failing_round_is_logged_and_the_loop_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = threading.Semaphore(0)

    def failing_round() -> None:
        calls.release()
        raise RuntimeError("synthetic failure")

    dispatcher = EmailDispatcher(failing_round, interval_seconds=0.01)
    with caplog.at_level(logging.ERROR, logger="app.email"):
        dispatcher.start()
        assert calls.acquire(timeout=2)
        assert calls.acquire(timeout=2)
        dispatcher.stop()

    assert "email_dispatch_round_failed" in caplog.messages
    assert "synthetic failure" not in caplog.text


def test_stop_without_start_is_harmless() -> None:
    EmailDispatcher(lambda: None, interval_seconds=1).stop()


def test_build_uses_the_configured_interval() -> None:
    dispatcher = build_email_dispatcher(Settings(email_dispatch_interval_seconds=7))

    assert dispatcher._interval_seconds == 7


class RecordingDispatcher:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


@pytest.mark.parametrize(
    ("enabled", "expected"), [(True, ["start", "stop"]), (False, [])]
)
def test_application_runs_the_dispatcher_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, expected: list[str]
) -> None:
    recorder = RecordingDispatcher()
    monkeypatch.setattr(main_module, "build_email_dispatcher", lambda _: recorder)
    application: FastAPI = create_app(Settings(email_dispatch_enabled=enabled))

    with TestClient(application):
        pass

    assert recorder.events == expected
