import pytest

from app.notifications.domain.notification_email import (
    notification_email,
    sends_email,
)
from app.notifications.domain.notification_type import NotificationType

APP_URL = "https://app.example.invalid"
IN_APP_MESSAGE = "Synthetic in-app message"


@pytest.mark.parametrize(
    ("notification_type", "expected"),
    [
        (NotificationType.APPLICATION_RECEIVED, True),
        (NotificationType.APPLICATION_STATUS_CHANGED, True),
        (NotificationType.CONTACT_RECEIVED, True),
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
    email = notification_email(
        notification_type, app_url=APP_URL, message=IN_APP_MESSAGE
    )

    assert email.subject == subject
    assert summary in email.body
    assert APP_URL in email.body
    assert IN_APP_MESSAGE not in email.body
    assert email.body.endswith("Não é preciso respondê-lo.")


def test_generic_email_text_depends_only_on_the_event_type() -> None:
    # A generic event ignores the in-app message, so no job, company,
    # candidate or reason in it can reach the e-mail.
    first = notification_email(
        NotificationType.APPLICATION_RECEIVED, app_url=APP_URL, message="First"
    )
    second = notification_email(
        NotificationType.APPLICATION_RECEIVED, app_url=APP_URL, message="Second"
    )

    assert first == second


def test_contact_email_carries_the_in_app_message() -> None:
    email = notification_email(
        NotificationType.CONTACT_RECEIVED, app_url=APP_URL, message=IN_APP_MESSAGE
    )

    assert email.subject == "Uma empresa entrou em contato com você"
    assert IN_APP_MESSAGE in email.body
    assert APP_URL in email.body


def test_contact_email_tells_the_professional_to_answer_outside_the_email() -> None:
    email = notification_email(
        NotificationType.CONTACT_RECEIVED, app_url=APP_URL, message=IN_APP_MESSAGE
    )

    assert "Não responda a esta mensagem" in email.body
    assert "não chegam à empresa" in email.body
    assert "pelo canal que ela informou na mensagem acima" in email.body
    assert "nunca pede CPF" in email.body
    assert "Não é preciso respondê-lo" not in email.body


def test_event_without_email_cannot_be_composed() -> None:
    with pytest.raises(KeyError):
        notification_email(
            NotificationType.COMPANY_REGISTRATION_REJECTED,
            app_url=APP_URL,
            message=IN_APP_MESSAGE,
        )
