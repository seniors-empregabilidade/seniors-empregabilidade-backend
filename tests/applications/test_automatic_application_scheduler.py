import logging
import threading
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.applications.services.apply_automatically_to_new_job as apply_module
import app.main as main_module
from app.applications.automatic_application_scheduler import (
    AutomaticApplicationScheduler,
    build_automatic_application_scheduler,
)
from app.core.config import Settings
from app.main import create_app


def test_scheduler_runs_on_start_and_again_every_interval() -> None:
    rounds = threading.Semaphore(0)
    scheduler = AutomaticApplicationScheduler(rounds.release, interval_seconds=0.01)

    scheduler.start()
    assert rounds.acquire(timeout=2)
    assert rounds.acquire(timeout=2)
    scheduler.stop()

    assert scheduler._thread is not None
    assert not scheduler._thread.is_alive()


def test_failing_round_is_logged_and_the_loop_continues(
    caplog: pytest.LogCaptureFixture,
) -> None:
    calls = threading.Semaphore(0)

    def failing_round() -> None:
        calls.release()
        raise RuntimeError("synthetic failure")

    scheduler = AutomaticApplicationScheduler(failing_round, interval_seconds=0.01)
    with caplog.at_level(logging.ERROR, logger="app.applications"):
        scheduler.start()
        assert calls.acquire(timeout=2)
        assert calls.acquire(timeout=2)
        scheduler.stop()

    assert "automatic_applications_failed" in caplog.messages
    assert "synthetic failure" not in caplog.text


def test_stop_without_start_is_harmless() -> None:
    AutomaticApplicationScheduler(lambda: None, interval_seconds=1).stop()


def test_build_uses_the_configured_interval() -> None:
    scheduler = build_automatic_application_scheduler(
        Settings(automatic_application_interval_seconds=7)
    )

    assert scheduler._interval_seconds == 7


class RecordingScheduler:
    def __init__(self) -> None:
        self.events: list[str] = []

    def start(self) -> None:
        self.events.append("start")

    def stop(self) -> None:
        self.events.append("stop")


@pytest.mark.parametrize(
    ("enabled", "expected"), [(True, ["start", "stop"]), (False, [])]
)
def test_application_runs_the_scheduler_only_when_enabled(
    monkeypatch: pytest.MonkeyPatch, enabled: bool, expected: list[str]
) -> None:
    recorder = RecordingScheduler()
    monkeypatch.setattr(
        main_module, "build_automatic_application_scheduler", lambda _: recorder
    )
    application: FastAPI = create_app(Settings(automatic_application_enabled=enabled))

    with TestClient(application):
        pass

    assert recorder.events == expected


def test_new_job_evaluation_failure_is_logged_and_never_raised(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    def failing_evaluation(*_: object, **__: object) -> int:
        raise RuntimeError("synthetic failure")

    monkeypatch.setattr(
        apply_module, "generate_automatic_applications_for_job", failing_evaluation
    )

    with caplog.at_level(logging.ERROR, logger="app.applications"):
        apply_module.apply_automatically_to_new_job(uuid4(), 70)

    assert "automatic_applications_failed" in caplog.messages
    assert "synthetic failure" not in caplog.text


@pytest.mark.parametrize("threshold", [0, 101])
def test_threshold_must_be_a_percentage_above_zero(threshold: int) -> None:
    with pytest.raises(ValueError, match="automatic_application_threshold_percent"):
        Settings(automatic_application_threshold_percent=threshold)


def test_threshold_defaults_to_seventy_percent() -> None:
    assert Settings().automatic_application_threshold_percent == 70
