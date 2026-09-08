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

from app.auth.exceptions import (
    AuthenticationChallengeRequiredError,
    AuthenticationError,
    IdentityProviderUnavailableError,
    InvalidCredentialsError,
    TooManyAttemptsError,
)
from app.auth.services.identity_provider import IdentityTokens
from app.core.config import Settings

if TYPE_CHECKING:
    from mypy_boto3_cognito_idp.client import CognitoIdentityProviderClient

# Every provider rejection that must read as "wrong email or password" to the
# caller. Account state is deliberately included: Cognito's ordering of state
# and password checks is not contractual, so a distinct code here could become
# a user-enumeration oracle.
_INVALID_CREDENTIALS_CODES: Final = frozenset(
    {
        "NotAuthorizedException",
        "UserNotFoundException",
        "UserNotConfirmedException",
        "PasswordResetRequiredException",
        # Reported when a password is refused by the pool policy. It is a
        # credential failure, not an unavailable provider.
        "InvalidPasswordException",
    }
)
_THROTTLED_CODES: Final = frozenset(
    {
        "TooManyRequestsException",
        "TooManyFailedAttemptsException",
        "LimitExceededException",
        "RequestLimitExceeded",
    }
)


@lru_cache
def build_cognito_client(region: str) -> CognitoIdentityProviderClient:
    """Build a shared Cognito client for the given AWS region.

    `InitiateAuth` is an unauthenticated user pool API, so the client is
    deliberately unsigned: sign-in needs no AWS credentials and no IAM policy on
    the machine running the API. Admin APIs are unreachable through it by design.

    Construction parses the service model and is expensive, and botocore clients
    are safe to share across threads once built, so instances are cached per
    region instead of being rebuilt on every request.
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


class CognitoIdentityProvider:
    """Verifies credentials against Amazon Cognito.

    Uses `USER_PASSWORD_AUTH`, so the app client in the user pool needs
    `ALLOW_USER_PASSWORD_AUTH` enabled.
    """

    def __init__(self, settings: Settings) -> None:
        if not settings.cognito_client_id:
            # Misconfiguration surfaces as a 502 on the first sign-in rather than
            # an import-time crash that would take the whole API down.
            raise IdentityProviderUnavailableError
        self._client_id = settings.cognito_client_id
        self._client_secret = settings.cognito_client_secret
        self._client = build_cognito_client(settings.cognito_region)

    def authenticate(self, *, email: str, password: str) -> IdentityTokens:
        parameters = {"USERNAME": email, "PASSWORD": password}
        if self._client_secret is not None:
            parameters["SECRET_HASH"] = self._secret_hash(email, self._client_secret)

        try:
            response = self._client.initiate_auth(
                AuthFlow="USER_PASSWORD_AUTH",
                ClientId=self._client_id,
                AuthParameters=parameters,
            )
        except ClientError as error:
            error_code = str(error.response.get("Error", {}).get("Code", ""))
            raise self._translate(error_code) from error
        except BotoCoreError as error:
            raise IdentityProviderUnavailableError from error

        # Cognito returns either a result or a challenge, never both. The
        # challenge carries a session token that completes authentication, so
        # nothing from that branch may reach the caller.
        if "AuthenticationResult" not in response:
            raise AuthenticationChallengeRequiredError

        result = response["AuthenticationResult"]
        access_token = result.get("AccessToken")
        id_token = result.get("IdToken")
        expires_in = result.get("ExpiresIn")
        token_type = result.get("TokenType")
        if (
            access_token is None
            or id_token is None
            or expires_in is None
            or token_type is None
        ):
            # Cognito populates all four on a successful sign-in, so an
            # incomplete result means the response cannot be trusted.
            raise IdentityProviderUnavailableError

        return IdentityTokens(
            access_token=access_token,
            id_token=id_token,
            refresh_token=result.get("RefreshToken"),
            expires_in=expires_in,
            token_type=token_type,
        )

    def _secret_hash(self, username: str, client_secret: SecretStr) -> str:
        # Must hash the exact string sent as USERNAME, or Cognito answers
        # NotAuthorizedException and the cause is invisible in the response.
        digest = hmac.new(
            key=client_secret.get_secret_value().encode("utf-8"),
            msg=f"{username}{self._client_id}".encode(),
            digestmod=hashlib.sha256,
        ).digest()
        return base64.b64encode(digest).decode("ascii")

    @staticmethod
    def _translate(error_code: str) -> AuthenticationError:
        # An allowlist with an unavailable default: a Cognito error code added in
        # a future API version can never be mistaken for valid credentials.
        if error_code in _INVALID_CREDENTIALS_CODES:
            return InvalidCredentialsError()
        if error_code in _THROTTLED_CODES:
            return TooManyAttemptsError()
        return IdentityProviderUnavailableError()
