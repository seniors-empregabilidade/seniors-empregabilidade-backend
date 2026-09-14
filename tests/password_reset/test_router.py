from collections.abc import Mapping

import pytest
from botocore.stub import Stubber
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity.dependencies import get_identity_provider
from app.identity.integrations.cognito import CognitoIdentityProvider
from tests.identity.fakes import FakeIdentityProvider

EMAIL = "person@example.invalid"
SEND_PATH = "/api/v1/password-reset/send"
DELIVERY = {
    "CodeDeliveryDetails": {
        "AttributeName": "email",
        "DeliveryMedium": "EMAIL",
        "Destination": "p***@e***",
    }
}


def comparable_headers(headers: Mapping[str, str]) -> dict[str, str]:
    volatile = {"date", "x-request-id"}
    return {
        name: value for name, value in headers.items() if name.lower() not in volatile
    }


@pytest.fixture
def fake_provider(application: FastAPI) -> FakeIdentityProvider:
    provider = FakeIdentityProvider()
    application.dependency_overrides[get_identity_provider] = lambda: provider
    return provider


@pytest.fixture
def cognito_provider(application: FastAPI) -> CognitoIdentityProvider:
    provider = CognitoIdentityProvider(
        region="us-east-2", pool_id="us-east-2_TestPool", client_id="testclient"
    )
    application.dependency_overrides[get_identity_provider] = lambda: provider
    return provider


def test_a_request_is_accepted_without_a_body(
    client: TestClient, fake_provider: FakeIdentityProvider
) -> None:
    response = client.post(SEND_PATH, json={"email": EMAIL})

    assert response.status_code == 202
    assert not response.content
    assert fake_provider.calls == ["start_reset"]


def test_the_address_is_normalised_before_reaching_the_provider(
    client: TestClient, cognito_provider: CognitoIdentityProvider
) -> None:
    with Stubber(cognito_provider._client) as stub:
        stub.add_response(
            "forgot_password",
            DELIVERY,
            {"ClientId": "testclient", "Username": EMAIL},
        )
        response = client.post(SEND_PATH, json={"email": f"  {EMAIL.upper()}  "})
        stub.assert_no_pending_responses()

    assert response.status_code == 202


@pytest.mark.parametrize(
    "provider_error",
    [
        "CodeDeliveryFailureException",
        "InvalidParameterException",
        "LimitExceededException",
        "NotAuthorizedException",
        "UserNotConfirmedException",
        "UserNotFoundException",
    ],
)
def test_an_account_specific_failure_is_answered_like_a_delivered_code(
    client: TestClient, cognito_provider: CognitoIdentityProvider, provider_error: str
) -> None:
    with Stubber(cognito_provider._client) as stub:
        stub.add_client_error(
            "forgot_password",
            service_error_code=provider_error,
            service_message="Synthetic provider detail must not reach the client.",
            expected_params={"ClientId": "testclient", "Username": EMAIL},
        )
        response = client.post(SEND_PATH, json={"email": EMAIL})
        stub.assert_no_pending_responses()

    assert response.status_code == 202
    assert not response.content


def test_a_delivered_code_and_an_unknown_address_are_indistinguishable(
    client: TestClient, cognito_provider: CognitoIdentityProvider
) -> None:
    with Stubber(cognito_provider._client) as stub:
        stub.add_response(
            "forgot_password", DELIVERY, {"ClientId": "testclient", "Username": EMAIL}
        )
        stub.add_client_error(
            "forgot_password", service_error_code="UserNotFoundException"
        )
        delivered = client.post(SEND_PATH, json={"email": EMAIL})
        unknown = client.post(SEND_PATH, json={"email": EMAIL})
        stub.assert_no_pending_responses()

    assert delivered.status_code == unknown.status_code
    assert delivered.content == unknown.content
    assert comparable_headers(delivered.headers) == comparable_headers(unknown.headers)


def test_global_throttling_is_reported_without_a_provider_message(
    client: TestClient, cognito_provider: CognitoIdentityProvider
) -> None:
    with Stubber(cognito_provider._client) as stub:
        stub.add_client_error(
            "forgot_password",
            service_error_code="TooManyRequestsException",
            service_message="Synthetic provider detail must not reach the client.",
        )
        response = client.post(SEND_PATH, json={"email": EMAIL})
        stub.assert_no_pending_responses()

    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["cache-control"] == "no-store"
    assert "www-authenticate" not in response.headers
    assert response.json() == {
        "type": "about:blank",
        "title": "Too Many Requests",
        "status": 429,
        "detail": "Too many attempts. Try again later.",
        "instance": SEND_PATH,
        "code": "too_many_attempts",
        "request_id": response.headers["x-request-id"],
    }


def test_an_unavailable_provider_is_reported_as_a_service_failure(
    client: TestClient, cognito_provider: CognitoIdentityProvider
) -> None:
    with Stubber(cognito_provider._client) as stub:
        stub.add_client_error(
            "forgot_password", service_error_code="InternalErrorException"
        )
        response = client.post(SEND_PATH, json={"email": EMAIL})
        stub.assert_no_pending_responses()

    assert response.status_code == 503
    assert response.json()["code"] == "identity_provider_unavailable"


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"email": ""},
        {"email": "missing-at-sign"},
        {"email": EMAIL, "unexpected": "value"},
    ],
)
def test_an_invalid_payload_is_refused_before_the_provider_is_called(
    client: TestClient, fake_provider: FakeIdentityProvider, payload: dict[str, str]
) -> None:
    response = client.post(SEND_PATH, json=payload)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"
    assert fake_provider.calls == []
