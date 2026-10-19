import logging

import pytest

from app.email.integrations.log import LogEmailSender

RECIPIENT = "person@synthetic.example.invalid"


def test_log_sender_records_the_event_without_personal_data(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="app.email"):
        LogEmailSender().send(to=RECIPIENT, subject="Assunto", body="Corpo secreto")

    assert [record.getMessage() for record in caplog.records] == ["email_logged"]
    logged = " ".join(f"{record.__dict__}" for record in caplog.records)
    assert RECIPIENT not in logged
    assert "Corpo secreto" not in logged
