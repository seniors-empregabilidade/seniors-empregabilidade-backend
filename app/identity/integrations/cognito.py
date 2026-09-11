import base64
import hashlib
import hmac
import re
from typing import Never, TypedDict

import boto3
import jwt
from botocore import UNSIGNED
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError

from app.identity.authenticated_identity import AuthenticatedIdentity
from app.identity.exceptions import (
    AuthenticationChallengeRequiredError,
    IdentityConfirmationRequiredError,
    IdentityConflictError,
    IdentityPasswordRejectedError,
    IdentityProviderUnavailableError,
    IdentityRateLimitError,
    InvalidAccessTokenError,
    InvalidConfirmationCodeError,
    InvalidCredentialsError,
)
from app.identity.registered_identity import RegisteredIdentity
from app.identity.tokens import IdentityTokens


class _SecretHash(TypedDict, total=False):
    SecretHash: str


class CognitoIdentityProvider:
    def __init__(
        self,
        *,
        region: str,
        pool_id: str,
        client_id: str,
        client_secret: str | None = None,
    ) -> None:
        if (
            not re.fullmatch(r"us-east-2_[A-Za-z0-9]+", pool_id)
            or region != "us-east-2"
            or not client_id
        ):
            raise IdentityProviderUnavailableError
        self._client_id = client_id
        self._client_secret = client_secret
        self._issuer = f"https://cognito-idp.{region}.amazonaws.com/{pool_id}"
        self._jwks = PyJWKClient(f"{self._issuer}/.well-known/jwks.json", timeout=3)
        self._client = boto3.client(
            "cognito-idp",
            region_name=region,
            config=Config(
                signature_version=UNSIGNED,
                connect_timeout=3,
                read_timeout=5,
                retries={"total_max_attempts": 1},
            ),
        )

    def _secret_hash(self, email: str) -> _SecretHash:
        if not self._client_secret:
            return {}
        digest = hmac.new(
            self._client_secret.encode(),
            (email + self._client_id).encode(),
            hashlib.sha256,
        ).digest()
        return {"SecretHash": base64.b64encode(digest).decode()}

    def register(self, *, email: str, password: str) -> RegisteredIdentity:
        try:
            result = self._client.sign_up(
                ClientId=self._client_id,
                Username=email,
                Password=password,
                UserAttributes=[{"Name": "email", "Value": email}],
                **self._secret_hash(email),
            )
            return RegisteredIdentity(result["UserSub"], result["UserConfirmed"])
        except ClientError as exc:
            if exc.response["Error"]["Code"] == "UsernameExistsException":
                # A retry may follow an ambiguous timeout or a local persistence failure.
                # A matching email alone never proves ownership of that identity.
                try:
                    identity = self.authenticate(email=email, password=password)
                except InvalidCredentialsError as cause:
                    raise IdentityConflictError from cause
                return RegisteredIdentity(identity.identity_subject, True)
            self._raise_provider_error(exc)
        except BotoCoreError as exc:
            raise IdentityProviderUnavailableError from exc

    def authenticate(self, *, email: str, password: str) -> AuthenticatedIdentity:
        parameters = {"USERNAME": email, "PASSWORD": password}
        if secret_hash := self._secret_hash(email):
            parameters["SECRET_HASH"] = secret_hash["SecretHash"]
        try:
            response = self._client.initiate_auth(
                ClientId=self._client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=parameters,
            )
        except ClientError as exc:
            self._raise_provider_error(exc)
        except BotoCoreError as exc:
            raise IdentityProviderUnavailableError from exc
        result = response.get("AuthenticationResult")
        if not result:
            raise AuthenticationChallengeRequiredError
        try:
            tokens = IdentityTokens(
                access_token=result["AccessToken"],
                id_token=result["IdToken"],
                refresh_token=result.get("RefreshToken"),
                expires_in=result["ExpiresIn"],
                token_type=result["TokenType"],
            )
        except KeyError as exc:
            raise IdentityProviderUnavailableError from exc
        subject = self.verify_access_token(tokens.access_token)
        return AuthenticatedIdentity(subject, tokens)

    def verify_access_token(self, token: str) -> str:
        if len(token) > 16384:
            raise InvalidAccessTokenError
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if (
                header.get("alg") != "RS256"
                or not isinstance(kid, str)
                or not 1 <= len(kid) <= 256
            ):
                raise InvalidAccessTokenError
            key = self._jwks.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                key.key,
                algorithms=["RS256"],
                issuer=self._issuer,
                options={
                    "verify_aud": False,
                    "require": ["exp", "iat", "iss", "sub", "token_use", "client_id"],
                },
            )
            subject = claims["sub"]
            if (
                claims["token_use"] != "access"
                or claims["client_id"] != self._client_id
                or not isinstance(subject, str)
                or not subject.strip()
            ):
                raise InvalidAccessTokenError
            return subject
        except PyJWKClientConnectionError as exc:
            raise IdentityProviderUnavailableError from exc
        except (jwt.PyJWTError, TypeError, ValueError) as exc:
            raise InvalidAccessTokenError from exc

    def confirm_email(self, *, email: str, code: str) -> None:
        try:
            self._client.confirm_sign_up(
                ClientId=self._client_id,
                Username=email,
                ConfirmationCode=code,
                **self._secret_hash(email),
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {
                "NotAuthorizedException",
                "UserNotFoundException",
            }:
                # Do not disclose account state or request login credentials here.
                raise InvalidConfirmationCodeError from exc
            self._raise_provider_error(exc)
        except BotoCoreError as exc:
            raise IdentityProviderUnavailableError from exc

    def resend_confirmation(self, *, email: str) -> None:
        try:
            self._client.resend_confirmation_code(
                ClientId=self._client_id,
                Username=email,
                **self._secret_hash(email),
            )
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {
                "UserNotFoundException",
                "InvalidParameterException",
                "NotAuthorizedException",
            }:
                return
            self._raise_provider_error(exc)
        except BotoCoreError as exc:
            raise IdentityProviderUnavailableError from exc

    @staticmethod
    def _raise_provider_error(exc: ClientError) -> Never:
        code = exc.response["Error"]["Code"]
        if code in {"NotAuthorizedException", "UserNotFoundException"}:
            raise InvalidCredentialsError from exc
        if code == "UserNotConfirmedException":
            raise IdentityConfirmationRequiredError from exc
        if code == "InvalidPasswordException":
            raise IdentityPasswordRejectedError from exc
        if code in {"TooManyRequestsException", "TooManyFailedAttemptsException"}:
            raise IdentityRateLimitError from exc
        if code in {"CodeMismatchException", "ExpiredCodeException"}:
            raise InvalidConfirmationCodeError from exc
        # LimitExceeded can mean SignUp created a user but email delivery failed.
        # Do not claim the operation had no side effect or reveal provider messages.
        raise IdentityProviderUnavailableError from exc
