import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from app.email.email_sender import EmailSendError


class SesEmailSender:
    """Sends through Amazon SES with the instance role's credentials.

    The sender address must be a verified SES identity, and while the account is
    in the SES sandbox only verified recipients receive messages.
    """

    def __init__(self, *, sender: str, region: str) -> None:
        self._sender = sender
        self._client = boto3.client(
            "sesv2",
            region_name=region,
            config=Config(
                connect_timeout=3,
                read_timeout=10,
                retries={"total_max_attempts": 2},
            ),
        )

    def send(self, *, to: str, subject: str, body: str) -> None:
        try:
            self._client.send_email(
                FromEmailAddress=self._sender,
                Destination={"ToAddresses": [to]},
                Content={
                    "Simple": {
                        "Subject": {"Data": subject, "Charset": "UTF-8"},
                        "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
                    }
                },
            )
        except ClientError as exc:
            raise EmailSendError(exc.response["Error"]["Code"]) from exc
        except BotoCoreError as exc:
            raise EmailSendError(type(exc).__name__) from exc
