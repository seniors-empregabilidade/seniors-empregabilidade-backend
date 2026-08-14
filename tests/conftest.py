from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db.session import dispose_engine
from app.main import create_app


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
