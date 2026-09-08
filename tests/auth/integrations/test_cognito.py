from dataclasses import dataclass, field
from typing import Any

import pytest
from botocore import UNSIGNED
from botocore.exceptions import (
    ClientError,
    EndpointConnectionError,
)
from pydantic import SecretStr

from app.auth import exceptions
from app.auth.integrations import cognito
from app.auth.integrations.cognito import CognitoIdentityProvider, build_cognito_client
from app.core.config import Settings

PROVIDER_MESSAGE = "Incorrect username or password."
SUCCESS_RESULT: dict[str, Any] = {
    "AuthenticationResult": {
        "AccessToken": "access-token-value",
        "IdToken": "id-token-value",
        "RefreshToken": "refresh-token-value",
        "ExpiresIn": 3600,
        "TokenType": "Bearer",
    }
}


@dataclass
class StubCognitoClient:
    response: dict[str, Any] | None = None
    error: Exception | None = None
    last_kwargs: dict[str, Any] = field(default_factory=dict)

    def initiate_auth(self, **kwargs: Any) -> Any:
        self.last_kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.response


def build_provider(
    monkeypatch: pytest.MonkeyPatch,
    stub: StubCognitoClient,
    *,
    client_secret: SecretStr | None = None,
) -> CognitoIdentityProvider:
    monkeypatch.setattr(cognito, "build_cognito_client", lambda region: stub)
    settings = Settings(
        cognito_region="us-east-1",
        cognito_client_id="client-123",
        cognito_client_secret=client_secret,
    )
    return CognitoIdentityProvider(settings)


def sign_in(provider: CognitoIdentityProvider) -> Any:
    return provider.authenticate(
        email="user@example.invalid", password="LocalDemoOnly!2026"
    )


def client_error(code: str) -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": PROVIDER_MESSAGE}}, "InitiateAuth"
    )


def test_a_successful_response_becomes_owned_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = build_provider(monkeypatch, StubCognitoClient(response=SUCCESS_RESULT))

    tokens = sign_in(provider)

    assert tokens.access_token == "access-token-value"
    assert tokens.id_token == "id-token-value"
    assert tokens.refresh_token == "refresh-token-value"
    assert tokens.expires_in == 3600
    assert tokens.token_type == "Bearer"


def test_the_configured_auth_flow_is_the_one_the_emulator_supports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubCognitoClient(response=SUCCESS_RESULT)

    sign_in(build_provider(monkeypatch, stub))

    assert stub.last_kwargs["AuthFlow"] == "USER_PASSWORD_AUTH"
    assert stub.last_kwargs["ClientId"] == "client-123"
    assert stub.last_kwargs["AuthParameters"]["USERNAME"] == "user@example.invalid"


@pytest.mark.parametrize(
    "code",
    [
        "NotAuthorizedException",
        "UserNotFoundException",
        "UserNotConfirmedException",
        "PasswordResetRequiredException",
        "InvalidPasswordException",
    ],
)
def test_every_credential_rejection_collapses_into_one_failure(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    provider = build_provider(monkeypatch, StubCognitoClient(error=client_error(code)))

    with pytest.raises(exceptions.InvalidCredentialsError) as failure:
        sign_in(provider)

    assert failure.value.status_code == 401
    assert failure.value.code == "invalid_credentials"
    assert PROVIDER_MESSAGE not in failure.value.detail


@pytest.mark.parametrize(
    "code",
    [
        "TooManyRequestsException",
        "TooManyFailedAttemptsException",
        "LimitExceededException",
        "RequestLimitExceeded",
    ],
)
def test_provider_throttling_is_reported_as_too_many_attempts(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    provider = build_provider(monkeypatch, StubCognitoClient(error=client_error(code)))

    with pytest.raises(exceptions.TooManyAttemptsError) as failure:
        sign_in(provider)

    assert failure.value.status_code == 429


@pytest.mark.parametrize(
    "code",
    [
        "InvalidParameterException",
        "ResourceNotFoundException",
        "UserLambdaValidationException",
        "InternalErrorException",
        "AnUnknownFutureCognitoCode",
    ],
)
def test_any_other_provider_error_never_reads_as_valid_credentials(
    monkeypatch: pytest.MonkeyPatch, code: str
) -> None:
    provider = build_provider(monkeypatch, StubCognitoClient(error=client_error(code)))

    with pytest.raises(exceptions.IdentityProviderUnavailableError) as failure:
        sign_in(provider)

    assert failure.value.status_code == 502
    assert PROVIDER_MESSAGE not in failure.value.detail


def test_a_transport_failure_is_reported_as_an_unavailable_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubCognitoClient(
        error=EndpointConnectionError(
            endpoint_url="https://cognito-idp.us-east-1.amazonaws.com"
        )
    )
    provider = build_provider(monkeypatch, stub)

    with pytest.raises(exceptions.IdentityProviderUnavailableError):
        sign_in(provider)


def test_a_challenge_never_reaches_the_caller(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    challenge: dict[str, Any] = {
        "ChallengeName": "NEW_PASSWORD_REQUIRED",
        "Session": "challenge-session-token",
        "ChallengeParameters": {"USER_ID_FOR_SRP": "user@example.invalid"},
    }
    provider = build_provider(monkeypatch, StubCognitoClient(response=challenge))

    with pytest.raises(exceptions.AuthenticationChallengeRequiredError) as failure:
        sign_in(provider)

    assert failure.value.status_code == 403
    assert "challenge-session-token" not in failure.value.detail


@pytest.mark.parametrize(
    "missing", ["AccessToken", "IdToken", "ExpiresIn", "TokenType"]
)
def test_a_result_without_a_usable_token_is_not_a_sign_in(
    monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    result = dict(SUCCESS_RESULT["AuthenticationResult"])
    del result[missing]
    provider = build_provider(
        monkeypatch, StubCognitoClient(response={"AuthenticationResult": result})
    )

    with pytest.raises(exceptions.IdentityProviderUnavailableError):
        sign_in(provider)


def test_no_secret_hash_is_sent_when_the_client_has_no_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubCognitoClient(response=SUCCESS_RESULT)

    sign_in(build_provider(monkeypatch, stub))

    assert "SECRET_HASH" not in stub.last_kwargs["AuthParameters"]


def test_the_secret_hash_matches_the_documented_algorithm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stub = StubCognitoClient(response=SUCCESS_RESULT)
    provider = build_provider(monkeypatch, stub, client_secret=SecretStr("test-secret"))

    sign_in(provider)

    assert stub.last_kwargs["AuthParameters"]["SECRET_HASH"] == (
        "o1ag8asuyY8+wu7gykssmJpxexlG0TGsPdEtJK7N0IQ="
    )


def test_an_unconfigured_client_id_fails_before_any_network_call() -> None:
    with pytest.raises(exceptions.IdentityProviderUnavailableError):
        CognitoIdentityProvider(Settings(cognito_client_id=""))


def test_the_client_targets_the_configured_aws_region() -> None:
    build_cognito_client.cache_clear()
    try:
        assert build_cognito_client("us-east-1").meta.endpoint_url == (
            "https://cognito-idp.us-east-1.amazonaws.com"
        )
        assert build_cognito_client("sa-east-1").meta.endpoint_url == (
            "https://cognito-idp.sa-east-1.amazonaws.com"
        )
    finally:
        build_cognito_client.cache_clear()


def test_sign_in_requires_no_aws_credentials() -> None:
    build_cognito_client.cache_clear()
    try:
        # InitiateAuth is an unauthenticated user pool API, so the client is
        # unsigned and never resolves the AWS credential chain. Botocore sets
        # Config attributes dynamically, hence getattr.
        config = build_cognito_client("us-east-1").meta.config
        assert getattr(config, "signature_version", None) is UNSIGNED
    finally:
        build_cognito_client.cache_clear()
