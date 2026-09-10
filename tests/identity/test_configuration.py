import json
from pathlib import Path

import boto3
import pytest
from botocore import UNSIGNED
from botocore.config import Config
from botocore.validate import validate_parameters
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.core.config import Settings
from app.identity.dependencies import _configured_provider, get_identity_provider


@pytest.mark.parametrize(
    "filename,operation",
    [("user-pool.json", "CreateUserPool"), ("app-client.json", "CreateUserPoolClient")],
)
def test_proposed_aws_inputs_match_locked_sdk(filename: str, operation: str) -> None:
    payload = json.loads(
        (
            Path(__file__).resolve().parents[2] / "infra" / "cognito" / filename
        ).read_text()
    )
    if "UserPoolId" in payload:
        payload["UserPoolId"] = "us-east-2_TestPool"
    client = boto3.client(
        "cognito-idp",
        region_name="us-east-2",
        config=Config(signature_version=UNSIGNED),
    )
    shape = client.meta.service_model.operation_model(operation).input_shape
    assert shape is not None
    validate_parameters(payload, shape)


def test_provider_composition_reuses_client_without_exposing_secret() -> None:
    settings = Settings(
        cognito_user_pool_id="us-east-2_TestPool",
        cognito_client_id="synthetic-client",
        cognito_client_secret=SecretStr("synthetic-private-secret"),
    )
    try:
        assert get_identity_provider(settings) is get_identity_provider(settings)
        assert "synthetic-private-secret" not in repr(settings)
    finally:
        _configured_provider.cache_clear()


def test_unconfigured_auth_is_503_and_health_still_works(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "synthetic@example.invalid", "password": "synthetic"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "identity_provider_unavailable"
    assert client.get("/health").status_code == 200
