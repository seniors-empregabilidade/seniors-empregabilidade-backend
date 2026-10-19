from dataclasses import dataclass

from app.notifications.domain.notification_type import NotificationType


@dataclass(frozen=True, slots=True)
class NotificationEmail:
    subject: str
    body: str


# Events that also produce an e-mail. Every other notification stays in-app only.
_EMAIL_COPY: dict[NotificationType, tuple[str, str]] = {
    NotificationType.APPLICATION_RECEIVED: (
        "Nova candidatura em uma vaga sua",
        "Uma das suas vagas recebeu uma nova candidatura.",
    ),
    NotificationType.APPLICATION_STATUS_CHANGED: (
        "Atualização em uma candidatura sua",
        "Uma das suas candidaturas teve o status atualizado.",
    ),
}


def sends_email(notification_type: NotificationType) -> bool:
    return notification_type in _EMAIL_COPY


def notification_email(
    notification_type: NotificationType, *, app_url: str
) -> NotificationEmail:
    """Compose the e-mail for an event that `sends_email`.

    The text is deliberately generic: no job title, company, candidate or reason
    leaves the platform by e-mail. The link opens the application, which asks
    the reader to sign in before showing anything private.
    """
    subject, summary = _EMAIL_COPY[notification_type]
    body = (
        "Olá!\n\n"
        f"{summary}\n\n"
        "Para ver os detalhes, entre na Seniors - Empregabilidade:\n"
        f"{app_url}\n\n"
        "Este é um e-mail automático. Não é preciso respondê-lo."
    )
    return NotificationEmail(subject=subject, body=body)
