import base64
import hashlib
import hmac
import json
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from botocore.exceptions import EndpointConnectionError
from botocore.stub import Stubber
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import PyJWKClientConnectionError

from app.core.errors import ProblemException
from app.identity.exceptions import (
    IdentityProviderUnavailableError,
    InvalidAccessTokenError,
)
from app.identity.integrations.cognito import CognitoIdentityProvider
from app.identity.registered_identity import RegisteredIdentity

EMAIL = "person@company.example.invalid"
PASSWORD = "SyntheticPassword!42"
SUBJECT = "11111111-2222-3333-4444-555555555555"
POOL = "us-east-2_TestPool"
CLIENT = "testclient"


@pytest.fixture
def provider() -> CognitoIdentityProvider:
    return CognitoIdentityProvider(region="us-east-2", pool_id=POOL, client_id=CLIENT)


@pytest.fixture
def stub(provider: CognitoIdentityProvider) -> Iterator[Stubber]:
    with Stubber(provider._client) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()


@pytest.fixture
def key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def access_token(key: rsa.RSAPrivateKey, **overrides: Any) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": SUBJECT,
        "iss": f"https://cognito-idp.us-east-2.amazonaws.com/{POOL}",
        "exp": now + timedelta(minutes=15),
        "iat": now,
        "client_id": CLIENT,
        "token_use": "access",
    }
    claims.update(overrides)
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test-key"})


def use_local_key(
    provider: CognitoIdentityProvider,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    jwk.update(kid="test-key", use="sig", alg="RS256")
    monkeypatch.setattr(provider._jwks, "fetch_data", lambda: {"keys": [jwk]})


def test_signup_sends_password_only_to_provider(
    provider: CognitoIdentityProvider, stub: Stubber
) -> None:
    stub.add_response(
        "sign_up",
        {"UserSub": SUBJECT, "UserConfirmed": False},
        {
            "ClientId": CLIENT,
            "Username": EMAIL,
            "Password": PASSWORD,
            "UserAttributes": [{"Name": "email", "Value": EMAIL}],
        },
    )
    result = provider.register(email=EMAIL, password=PASSWORD)
    assert result == RegisteredIdentity(SUBJECT, False)
    assert PASSWORD not in repr(result)


def test_confidential_client_secret_hash(
    provider: CognitoIdentityProvider, stub: Stubber
) -> None:
    provider._client_secret = "synthetic-secret"
    digest = hmac.new(
        b"synthetic-secret", (EMAIL + CLIENT).encode(), hashlib.sha256
    ).digest()
    stub.add_response(
        "resend_confirmation_code",
        {},
        {
            "ClientId": CLIENT,
            "Username": EMAIL,
            "SecretHash": base64.b64encode(digest).decode(),
        },
    )
    provider.resend_confirmation(email=EMAIL)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("InvalidPasswordException", "password_policy_violation"),
        ("TooManyRequestsException", "too_many_attempts"),
        ("TooManyFailedAttemptsException", "too_many_attempts"),
        ("LimitExceededException", "identity_provider_unavailable"),
        ("InternalErrorException", "identity_provider_unavailable"),
    ],
)
def test_signup_errors_do_not_expose_provider_messages(
    provider: CognitoIdentityProvider, stub: Stubber, code: str, expected: str
) -> None:
    stub.add_client_error("sign_up", service_error_code=code, service_message=PASSWORD)
    with pytest.raises(ProblemException) as error:
        provider.register(email=EMAIL, password=PASSWORD)
    assert error.value.code == expected
    assert PASSWORD not in error.value.detail


def test_access_token_signature_and_subject(
    provider: CognitoIdentityProvider,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_local_key(provider, key, monkeypatch)
    assert provider.verify_access_token(access_token(key)) == SUBJECT


@pytest.mark.parametrize(
    "claims",
    [
        {"token_use": "id"},
        {"client_id": "other-client"},
        {"iss": "https://attacker.example.invalid"},
        {"exp": 1},
        {"iat": 9999999999},
        {"sub": ""},
        {"sub": " "},
        {"sub": 42},
    ],
)
def test_rejects_wrong_token_claims(
    provider: CognitoIdentityProvider,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
    claims: dict[str, object],
) -> None:
    use_local_key(provider, key, monkeypatch)
    with pytest.raises(InvalidAccessTokenError):
        provider.verify_access_token(access_token(key, **claims))


def test_rejects_forged_signature(
    provider: CognitoIdentityProvider,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_local_key(provider, key, monkeypatch)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(InvalidAccessTokenError):
        provider.verify_access_token(access_token(other))


@pytest.mark.parametrize(
    "token",
    [
        "invalid",
        "x" * 16385,
        jwt.encode({"sub": SUBJECT}, "synthetic" * 4, algorithm="HS256"),
    ],
)
def test_rejects_malformed_or_wrong_algorithm_without_network(
    provider: CognitoIdentityProvider, token: str
) -> None:
    with pytest.raises(InvalidAccessTokenError):
        provider.verify_access_token(token)


def test_jwks_outage_is_503(
    provider: CognitoIdentityProvider,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable() -> object:
        raise PyJWKClientConnectionError("synthetic")

    monkeypatch.setattr(provider._jwks, "fetch_data", unavailable)
    with pytest.raises(IdentityProviderUnavailableError):
        provider.verify_access_token(access_token(key))


def test_authentication_verifies_returned_access_token(
    provider: CognitoIdentityProvider,
    stub: Stubber,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_local_key(provider, key, monkeypatch)
    token = access_token(key)
    stub.add_response(
        "initiate_auth",
        {
            "AuthenticationResult": {
                "AccessToken": token,
                "IdToken": "synthetic-id",
                "RefreshToken": "synthetic-refresh",
                "ExpiresIn": 900,
                "TokenType": "Bearer",
            }
        },
        {
            "ClientId": CLIENT,
            "AuthFlow": "USER_PASSWORD_AUTH",
            "AuthParameters": {"USERNAME": EMAIL, "PASSWORD": PASSWORD},
        },
    )
    result = provider.authenticate(email=EMAIL, password=PASSWORD)
    assert result.identity_subject == SUBJECT
    assert result.tokens.access_token == token
    assert token not in repr(result)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("NotAuthorizedException", "invalid_credentials"),
        ("UserNotFoundException", "invalid_credentials"),
        ("UserNotConfirmedException", "identity_confirmation_required"),
    ],
)
def test_authentication_errors(
    provider: CognitoIdentityProvider, stub: Stubber, code: str, expected: str
) -> None:
    stub.add_client_error("initiate_auth", service_error_code=code)
    with pytest.raises(ProblemException) as error:
        provider.authenticate(email=EMAIL, password=PASSWORD)
    assert error.value.code == expected


def test_challenges_are_not_a_successful_login(
    provider: CognitoIdentityProvider, stub: Stubber
) -> None:
    stub.add_response(
        "initiate_auth", {"ChallengeName": "NEW_PASSWORD_REQUIRED", "Session": "s" * 20}
    )
    with pytest.raises(ProblemException, match="additional sign-in"):
        provider.authenticate(email=EMAIL, password=PASSWORD)


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("NotAuthorizedException", "identity_conflict"),
        ("UserNotConfirmedException", "identity_confirmation_required"),
    ],
)
def test_existing_email_does_not_establish_identity_ownership(
    provider: CognitoIdentityProvider, stub: Stubber, code: str, expected: str
) -> None:
    stub.add_client_error("sign_up", service_error_code="UsernameExistsException")
    stub.add_client_error("initiate_auth", service_error_code=code)
    with pytest.raises(ProblemException) as error:
        provider.register(email=EMAIL, password=PASSWORD)
    assert error.value.code == expected


def test_retry_reuses_only_a_proven_confirmed_identity(
    provider: CognitoIdentityProvider,
    stub: Stubber,
    key: rsa.RSAPrivateKey,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_local_key(provider, key, monkeypatch)
    stub.add_client_error("sign_up", service_error_code="UsernameExistsException")
    stub.add_response(
        "initiate_auth",
        {
            "AuthenticationResult": {
                "AccessToken": access_token(key),
                "IdToken": "id",
                "ExpiresIn": 900,
                "TokenType": "Bearer",
            }
        },
    )
    assert provider.register(email=EMAIL, password=PASSWORD) == RegisteredIdentity(
        SUBJECT, True
    )


def test_confirm_email(provider: CognitoIdentityProvider, stub: Stubber) -> None:
    stub.add_response(
        "confirm_sign_up",
        {},
        {"ClientId": CLIENT, "Username": EMAIL, "ConfirmationCode": "123456"},
    )
    provider.confirm_email(email=EMAIL, code="123456")


@pytest.mark.parametrize(
    "code",
    [
        "CodeMismatchException",
        "ExpiredCodeException",
        "NotAuthorizedException",
        "UserNotFoundException",
    ],
)
def test_confirmation_error(
    provider: CognitoIdentityProvider, stub: Stubber, code: str
) -> None:
    stub.add_client_error("confirm_sign_up", service_error_code=code)
    with pytest.raises(ProblemException) as error:
        provider.confirm_email(email=EMAIL, code="123456")
    assert error.value.code == "invalid_verification_code"
    assert error.value.status_code == 422
    assert error.value.errors == {
        "code": ["The verification code is invalid or expired."]
    }


@pytest.mark.parametrize(
    "code",
    ["UserNotFoundException", "InvalidParameterException", "NotAuthorizedException"],
)
def test_resend_does_not_disclose_account_existence(
    provider: CognitoIdentityProvider, stub: Stubber, code: str
) -> None:
    stub.add_client_error("resend_confirmation_code", service_error_code=code)
    provider.resend_confirmation(email=EMAIL)


@pytest.mark.parametrize(
    "operation",
    ["sign_up", "initiate_auth", "confirm_sign_up", "resend_confirmation_code"],
)
def test_connection_errors(
    provider: CognitoIdentityProvider, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    def unavailable(**kwargs: object) -> None:
        raise EndpointConnectionError(endpoint_url="https://synthetic.example.invalid")

    monkeypatch.setattr(provider._client, operation, unavailable)
    with pytest.raises(IdentityProviderUnavailableError):
        if operation == "sign_up":
            provider.register(email=EMAIL, password=PASSWORD)
        elif operation == "initiate_auth":
            provider.authenticate(email=EMAIL, password=PASSWORD)
        elif operation == "confirm_sign_up":
            provider.confirm_email(email=EMAIL, code="123456")
        else:
            provider.resend_confirmation(email=EMAIL)


@pytest.mark.parametrize(
    "region,pool,client",
    [("us-east-1", POOL, CLIENT), ("us-east-2", "", CLIENT), ("us-east-2", POOL, "")],
)
def test_unconfigured_identity_is_unavailable(
    region: str, pool: str, client: str
) -> None:
    with pytest.raises(IdentityProviderUnavailableError):
        CognitoIdentityProvider(region=region, pool_id=pool, client_id=client)
