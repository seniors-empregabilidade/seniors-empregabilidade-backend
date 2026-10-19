import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.email.dependencies import build_email_sender
from app.email.integrations.log import LogEmailSender
from app.email.integrations.ses import SesEmailSender


def test_log_backend_is_the_default() -> None:
    assert isinstance(build_email_sender(Settings()), LogEmailSender)


def test_ses_backend_builds_the_ses_sender() -> None:
    settings = Settings(
        email_backend="ses", email_sender_address="no-reply@seniors.example.invalid"
    )

    assert isinstance(build_email_sender(settings), SesEmailSender)


@pytest.mark.parametrize("address", ["", "   "])
def test_ses_backend_requires_a_sender_address(address: str) -> None:
    with pytest.raises(ValidationError, match="EMAIL_SENDER_ADDRESS"):
        Settings(email_backend="ses", email_sender_address=address)
