from collections.abc import Iterator

import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber

from app.email.email_sender import EmailSendError
from app.email.integrations.ses import SesEmailSender

SENDER = "no-reply@seniors.example.invalid"
RECIPIENT = "person@synthetic.example.invalid"


@pytest.fixture
def sender(monkeypatch: pytest.MonkeyPatch) -> SesEmailSender:
    # Production signs with the instance role; tests need any static pair.
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "synthetic")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "synthetic")
    return SesEmailSender(sender=SENDER, region="us-east-2")


@pytest.fixture
def stub(sender: SesEmailSender) -> Iterator[Stubber]:
    with Stubber(sender._client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


def test_send_uses_plain_utf8_text(sender: SesEmailSender, stub: Stubber) -> None:
    stub.add_response(
        "send_email",
        {"MessageId": "synthetic-message"},
        {
            "FromEmailAddress": SENDER,
            "Destination": {"ToAddresses": [RECIPIENT]},
            "Content": {
                "Simple": {
                    "Subject": {"Data": "Assunto", "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": "Corpo", "Charset": "UTF-8"}},
                }
            },
        },
    )

    sender.send(to=RECIPIENT, subject="Assunto", body="Corpo")


def test_rejection_keeps_only_the_provider_code(
    sender: SesEmailSender, stub: Stubber
) -> None:
    stub.add_client_error(
        "send_email",
        service_error_code="MessageRejected",
        service_message=f"Email address is not verified: {RECIPIENT}",
    )

    with pytest.raises(EmailSendError) as error:
        sender.send(to=RECIPIENT, subject="Assunto", body="Corpo")

    assert error.value.code == "MessageRejected"
    assert RECIPIENT not in str(error.value)


def test_network_failure_becomes_a_send_error(
    sender: SesEmailSender, monkeypatch: pytest.MonkeyPatch
) -> None:
    def unreachable(**_: object) -> None:
        raise EndpointConnectionError(endpoint_url="https://email.invalid")

    monkeypatch.setattr(sender._client, "send_email", unreachable)

    with pytest.raises(EmailSendError) as error:
        sender.send(to=RECIPIENT, subject="Assunto", body="Corpo")

    assert error.value.code == "EndpointConnectionError"
