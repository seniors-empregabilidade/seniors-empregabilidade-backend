import pytest
from botocore.stub import Stubber
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity.dependencies import get_identity_provider
from app.identity.integrations.cognito import CognitoIdentityProvider


@pytest.mark.parametrize(
    "provider_error",
    [
        "CodeMismatchException",
        "ExpiredCodeException",
        "NotAuthorizedException",
        "UserNotFoundException",
    ],
)
def test_confirmation_failures_share_a_field_error_without_authentication_challenge(
    application: FastAPI, client: TestClient, provider_error: str
) -> None:
    provider = CognitoIdentityProvider(
        region="us-east-2", pool_id="us-east-2_TestPool", client_id="testclient"
    )
    application.dependency_overrides[get_identity_provider] = lambda: provider
    path = "/api/v1/email-verification/confirm"
    with Stubber(provider._client) as stub:
        stub.add_client_error(
            "confirm_sign_up",
            service_error_code=provider_error,
            service_message="Synthetic provider detail must not reach the client.",
            expected_params={
                "ClientId": "testclient",
                "Username": "person@example.invalid",
                "ConfirmationCode": "123456",
            },
        )
        response = client.post(
            path, json={"email": "person@example.invalid", "code": "123456"}
        )
        stub.assert_no_pending_responses()

    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert "www-authenticate" not in response.headers
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "type": "about:blank",
        "title": "Validation Error",
        "status": 422,
        "detail": "The verification code is invalid or expired.",
        "instance": path,
        "code": "invalid_verification_code",
        "request_id": response.headers["x-request-id"],
        "errors": {"code": ["The verification code is invalid or expired."]},
    }
