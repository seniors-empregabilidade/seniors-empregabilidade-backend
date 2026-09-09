import base64
import hashlib
import hmac
from functools import lru_cache
from typing import TYPE_CHECKING, Final

import boto3
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import SecretStr

from app.accounts.exceptions import (
    EmailVerificationError,
    EmailVerificationProviderUnavailableError,
    InvalidVerificationCodeError,
    ResendLimitReachedError,
    TooManyVerificationAttemptsError,
    VerificationCodeExpiredError,
)
from app.core.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient

# Rejections that must leave `send_code` silent. An address that cannot receive a
# code is indistinguishable from one that can, so this endpoint cannot be used to
# enumerate accounts. `InvalidParameterException` is included because Cognito uses
# it for an already-confirmed user, at the cost of also swallowing a malformed
# username; the confirm path still surfaces real configuration errors.
_SILENT_SEND_CODES: Final = frozenset(
    {
        "UserNotFoundException",
        "NotAuthorizedException",
        "InvalidParameterException",
    }
)
_THROTTLED_CODES: Final = frozenset(
    {
        "TooManyRequestsException",
        "LimitExceededException",
        "RequestLimitExceeded",
    }
)
# Every confirm rejection that must read as "wrong code" to the caller. An unknown
# user is included deliberately: a distinct answer there would reveal which
# addresses exist.
_INVALID_CODE_CODES: Final = frozenset(
    {
        "CodeMismatchException",
        "UserNotFoundException",
        "NotAuthorizedException",
    }
)


@lru_cache
def build_cognito_client(region: str) -> CognitoIdentityProviderClient:
    """Build a shared Cognito client for the given AWS region.

    `ResendConfirmationCode` and `ConfirmSignUp` are unauthenticated user pool
    APIs, so the client is deliberately unsigned: verification needs no AWS
    credentials and no IAM policy on the machine running the API. Admin APIs are
    unreachable through it by design.

    Duplicated from the sign-in adapter while both live on separate branches;
    collapse into one shared builder once they meet on `main`.
    """
    return boto3.client(
        "cognito-idp",
        region_name=region,
        config=Config(
            signature_version=UNSIGNED,
            retries={"max_attempts": 2, "mode": "standard"},
            connect_timeout=3,
            read_timeout=5,
        ),
    )


class CognitoEmailVerificationProvider:
    """Sends and confirms verification codes through an Amazon Cognito user pool.

    The pool owns the code: it generates it, delivers the email, enforces its own
    expiry, and validates it. Nothing about a code is stored or logged here.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.cognito_client_id:
            # Misconfiguration surfaces as a 502 on the first call rather than an
            # import-time crash that would take the whole API down.
            raise EmailVerificationProviderUnavailableError
        self._client_id = settings.cognito_client_id
        self._client_secret = settings.cognito_client_secret
        self._client = build_cognito_client(settings.cognito_region)

    def send_code(self, *, email: str) -> None:
        secret_hash = self._secret_hash_or_none(email)
        try:
            if secret_hash is None:
                self._client.resend_confirmation_code(
                    ClientId=self._client_id,
                    Username=email,
                )
            else:
                self._client.resend_confirmation_code(
                    ClientId=self._client_id,
                    Username=email,
                    SecretHash=secret_hash,
                )
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            if error_code in _SILENT_SEND_CODES:
                return
            if error_code in _THROTTLED_CODES:
                raise ResendLimitReachedError from error
            raise EmailVerificationProviderUnavailableError from error
        except BotoCoreError as error:
            raise EmailVerificationProviderUnavailableError from error

    def confirm_code(self, *, email: str, code: str) -> None:
        secret_hash = self._secret_hash_or_none(email)
        try:
            if secret_hash is None:
                self._client.confirm_sign_up(
                    ClientId=self._client_id,
                    Username=email,
                    ConfirmationCode=code,
                )
            else:
                self._client.confirm_sign_up(
                    ClientId=self._client_id,
                    Username=email,
                    ConfirmationCode=code,
                    SecretHash=secret_hash,
                )
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            raise self._translate_confirm(error_code) from error
        except BotoCoreError as error:
            raise EmailVerificationProviderUnavailableError from error

    def _secret_hash_or_none(self, username: str) -> str | None:
        if self._client_secret is None:
            return None
        return self._secret_hash(username, self._client_secret)

    def _secret_hash(self, username: str, client_secret: SecretStr) -> str:
        # Must hash the exact string sent as Username, or Cognito answers
        # NotAuthorizedException and the cause is invisible in the response.
        digest = hmac.new(
            key=client_secret.get_secret_value().encode("utf-8"),
            msg=f"{username}{self._client_id}".encode(),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    @staticmethod
    def _translate_confirm(error_code: str) -> EmailVerificationError:
        # An allowlist with an unavailable default: a Cognito error code added in
        # a future API version can never be mistaken for an accepted code.
        if error_code == "ExpiredCodeException":
            return VerificationCodeExpiredError()
        if error_code == "TooManyFailedAttemptsException":
            return TooManyVerificationAttemptsError()
        if error_code in _INVALID_CODE_CODES:
            return InvalidVerificationCodeError()
        if error_code in _THROTTLED_CODES:
            return TooManyVerificationAttemptsError()
        return EmailVerificationProviderUnavailableError()
