from app.core.config import Settings
from app.email.email_sender import EmailSender
from app.email.integrations.log import LogEmailSender
from app.email.integrations.ses import SesEmailSender


def build_email_sender(settings: Settings) -> EmailSender:
    if settings.email_backend == "ses":
        return SesEmailSender(
            sender=settings.email_sender_address, region=settings.email_region
        )
    return LogEmailSender()
