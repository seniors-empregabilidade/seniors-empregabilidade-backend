from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import dispose_engine
from app.main import create_app


@pytest.fixture(autouse=True)
def isolate_identity_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    # A developer may have a real pool configured in their ignored .env.
    monkeypatch.setenv("COGNITO_REGION", "us-east-2")
    monkeypatch.setenv("COGNITO_USER_POOL_ID", "")
    monkeypatch.setenv("COGNITO_CLIENT_ID", "")
    monkeypatch.setenv("COGNITO_CLIENT_SECRET", "")


@pytest.fixture
def application() -> Iterator[FastAPI]:
    get_settings.cache_clear()
    dispose_engine()
    app = create_app()
    yield app
    dispose_engine()
    get_settings.cache_clear()


@pytest.fixture
def client(application: FastAPI) -> Iterator[TestClient]:
    with TestClient(application, raise_server_exceptions=False) as test_client:
        yield test_client
