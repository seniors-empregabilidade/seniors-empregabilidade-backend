from typing import Any

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from pydantic import SecretStr

from app.accounts.exceptions import (
    EmailVerificationProviderUnavailableError,
    InvalidVerificationCodeError,
    ResendLimitReachedError,
    TooManyVerificationAttemptsError,
    VerificationCodeExpiredError,
)
from app.accounts.integrations import cognito_email_verification
from app.accounts.integrations.cognito_email_verification import (
    CognitoEmailVerificationProvider,
)
from app.core.config import Settings

EMAIL = "person@example.invalid"


class FakeCognitoClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.error: Exception | None = None

    def resend_confirmation_code(self, **kwargs: Any) -> None:
        self.calls.append(("resend_confirmation_code", kwargs))
        if self.error is not None:
            raise self.error

    def confirm_sign_up(self, **kwargs: Any) -> None:
        self.calls.append(("confirm_sign_up", kwargs))
        if self.error is not None:
            raise self.error


def client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code}}, "CognitoOperation")


@pytest.fixture
def cognito_client(monkeypatch: pytest.MonkeyPatch) -> FakeCognitoClient:
    client = FakeCognitoClient()
    monkeypatch.setattr(
        cognito_email_verification,
        "build_cognito_client",
        lambda region: client,
    )
    return client


@pytest.fixture
def cognito_provider(
    cognito_client: FakeCognitoClient,
) -> CognitoEmailVerificationProvider:
    settings = Settings(cognito_client_id="test-client-id", cognito_client_secret=None)
    return CognitoEmailVerificationProvider(settings)


def test_an_unconfigured_client_id_reports_the_provider_as_unavailable(
    cognito_client: FakeCognitoClient,
) -> None:
    settings = Settings(cognito_client_id="")

    with pytest.raises(EmailVerificationProviderUnavailableError):
        CognitoEmailVerificationProvider(settings)


def test_sending_calls_cognito_without_a_secret_hash(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
) -> None:
    cognito_provider.send_code(email=EMAIL)

    operation, arguments = cognito_client.calls[0]
    assert operation == "resend_confirmation_code"
    assert arguments == {"ClientId": "test-client-id", "Username": EMAIL}


def test_a_configured_secret_is_sent_as_a_hash_never_as_itself(
    cognito_client: FakeCognitoClient,
) -> None:
    settings = Settings(
        cognito_client_id="test-client-id",
        cognito_client_secret=SecretStr("top-secret"),
    )
    provider = CognitoEmailVerificationProvider(settings)

    provider.send_code(email=EMAIL)

    _, arguments = cognito_client.calls[0]
    assert "SecretHash" in arguments
    assert arguments["SecretHash"] != "top-secret"
    assert "top-secret" not in str(arguments)


@pytest.mark.parametrize(
    "error_code",
    ["UserNotFoundException", "NotAuthorizedException", "InvalidParameterException"],
)
def test_sending_stays_silent_for_addresses_that_cannot_receive_a_code(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
    error_code: str,
) -> None:
    cognito_client.error = client_error(error_code)

    cognito_provider.send_code(email=EMAIL)


@pytest.mark.parametrize(
    "error_code",
    ["TooManyRequestsException", "LimitExceededException", "RequestLimitExceeded"],
)
def test_a_throttled_send_reports_the_resend_limit(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
    error_code: str,
) -> None:
    cognito_client.error = client_error(error_code)

    with pytest.raises(ResendLimitReachedError):
        cognito_provider.send_code(email=EMAIL)


def test_an_unrecognised_send_failure_reports_the_provider_as_unavailable(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
) -> None:
    cognito_client.error = client_error("SomeFutureCognitoException")

    with pytest.raises(EmailVerificationProviderUnavailableError):
        cognito_provider.send_code(email=EMAIL)


@pytest.mark.parametrize(
    ("error_code", "expected"),
    [
        ("CodeMismatchException", InvalidVerificationCodeError),
        ("UserNotFoundException", InvalidVerificationCodeError),
        ("NotAuthorizedException", InvalidVerificationCodeError),
        ("ExpiredCodeException", VerificationCodeExpiredError),
        ("TooManyFailedAttemptsException", TooManyVerificationAttemptsError),
        ("TooManyRequestsException", TooManyVerificationAttemptsError),
        ("SomeFutureCognitoException", EmailVerificationProviderUnavailableError),
    ],
)
def test_confirmation_failures_map_to_the_documented_contract(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
    error_code: str,
    expected: type[Exception],
) -> None:
    cognito_client.error = client_error(error_code)

    with pytest.raises(expected):
        cognito_provider.confirm_code(email=EMAIL, code="123456")


def test_a_network_failure_reports_the_provider_as_unavailable(
    cognito_provider: CognitoEmailVerificationProvider,
    cognito_client: FakeCognitoClient,
) -> None:
    cognito_client.error = EndpointConnectionError(endpoint_url="https://cognito.test")

    with pytest.raises(EmailVerificationProviderUnavailableError):
        cognito_provider.confirm_code(email=EMAIL, code="123456")
