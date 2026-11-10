from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider

ADMIN_PATH = "/api/v1/admin/trainings"
PUBLIC_PATH = "/api/v1/trainings"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", ADMIN_PATH),
        ("POST", ADMIN_PATH),
        ("GET", f"{ADMIN_PATH}/{uuid4()}"),
        ("PATCH", f"{ADMIN_PATH}/{uuid4()}"),
        ("DELETE", f"{ADMIN_PATH}/{uuid4()}"),
        ("GET", PUBLIC_PATH),
    ],
)
def test_every_training_route_requires_authentication(
    application: FastAPI, method: str, path: str
) -> None:
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider
    client = TestClient(application, raise_server_exceptions=False)
    response = client.request(method, path, json={} if method != "GET" else None)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/problem+json")
