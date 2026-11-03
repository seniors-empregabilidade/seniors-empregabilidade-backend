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
    NotificationType.CONTACT_RECEIVED: (
        "Uma empresa entrou em contato com você",
        "Uma empresa entrou em contato com você sobre uma vaga.",
    ),
}

# Events whose e-mail carries the notification message itself. The producer
# composes that message for the recipient and keeps it free of anyone's
# identification or contact data (see `app/contacts`).
_CARRIES_MESSAGE: frozenset[NotificationType] = frozenset(
    {NotificationType.CONTACT_RECEIVED}
)


_DEFAULT_FOOTER = "Este é um e-mail automático. Não é preciso respondê-lo."

# Footers for events whose reader may want to answer someone. The e-mail has no
# Reply-To and the sender mailbox is not read, so the reader is told where to
# answer instead.
_FOOTERS: dict[NotificationType, str] = {
    NotificationType.CONTACT_RECEIVED: (
        "Este é um e-mail automático. Não responda a esta mensagem: as respostas "
        "enviadas para este endereço não chegam à empresa.\n"
        "Se tiver interesse na vaga, entre em contato com a empresa pelo canal "
        "que ela informou na mensagem acima, fora deste e-mail.\n"
        "A Seniors - Empregabilidade nunca pede CPF, documentos, senhas ou dados "
        "bancários por e-mail."
    ),
}


def sends_email(notification_type: NotificationType) -> bool:
    return notification_type in _EMAIL_COPY


def notification_email(
    notification_type: NotificationType, *, app_url: str, message: str
) -> NotificationEmail:
    """Compose the e-mail for an event that `sends_email`.

    Most events are deliberately generic: no job title, company, candidate or
    reason leaves the platform by e-mail, and `message` is ignored. The events in
    `_CARRIES_MESSAGE` exist to deliver a message, so their e-mail repeats the
    in-app text, and their footer says where to answer instead of replying to
    the e-mail (see `_FOOTERS`). The link opens the application, which asks the reader to sign
    in before showing anything private.
    """
    subject, summary = _EMAIL_COPY[notification_type]
    if notification_type in _CARRIES_MESSAGE:
        summary = message
    body = (
        "Olá!\n\n"
        f"{summary}\n\n"
        "Para ver os detalhes, entre na Seniors - Empregabilidade:\n"
        f"{app_url}\n\n"
        f"{_FOOTERS.get(notification_type, _DEFAULT_FOOTER)}"
    )
    return NotificationEmail(subject=subject, body=body)
