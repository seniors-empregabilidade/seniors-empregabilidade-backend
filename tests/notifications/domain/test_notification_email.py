import pytest

from app.notifications.domain.notification_email import (
    notification_email,
    sends_email,
)
from app.notifications.domain.notification_type import NotificationType

APP_URL = "https://app.example.invalid"


@pytest.mark.parametrize(
    ("notification_type", "expected"),
    [
        (NotificationType.APPLICATION_RECEIVED, True),
        (NotificationType.APPLICATION_STATUS_CHANGED, True),
        (NotificationType.COMPANY_REGISTRATION_REJECTED, False),
    ],
)
def test_only_configured_events_send_email(
    notification_type: NotificationType, expected: bool
) -> None:
    assert sends_email(notification_type) is expected


@pytest.mark.parametrize(
    ("notification_type", "subject", "summary"),
    [
        (
            NotificationType.APPLICATION_RECEIVED,
            "Nova candidatura em uma vaga sua",
            "Uma das suas vagas recebeu uma nova candidatura.",
        ),
        (
            NotificationType.APPLICATION_STATUS_CHANGED,
            "Atualização em uma candidatura sua",
            "Uma das suas candidaturas teve o status atualizado.",
        ),
    ],
)
def test_email_is_generic_and_links_to_the_application(
    notification_type: NotificationType, subject: str, summary: str
) -> None:
    email = notification_email(notification_type, app_url=APP_URL)

    assert email.subject == subject
    assert summary in email.body
    assert APP_URL in email.body


def test_email_text_depends_only_on_the_event_type() -> None:
    # The composer receives no job, company, candidate or reason, so none of
    # them can reach the message.
    first = notification_email(NotificationType.APPLICATION_RECEIVED, app_url=APP_URL)
    second = notification_email(NotificationType.APPLICATION_RECEIVED, app_url=APP_URL)

    assert first == second


def test_event_without_email_cannot_be_composed() -> None:
    with pytest.raises(KeyError):
        notification_email(
            NotificationType.COMPANY_REGISTRATION_REJECTED, app_url=APP_URL
        )
