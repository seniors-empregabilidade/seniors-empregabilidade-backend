import re

import pytest
from fastapi.testclient import TestClient

import app.health.router as health_router
from app.core.middleware import REQUEST_ID_HEADER


def test_liveness_returns_ok_and_a_request_id(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        response.headers[REQUEST_ID_HEADER],
    )


def test_readiness_returns_ok_when_postgres_is_available(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health_router, "is_database_ready", lambda: True)

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_problem_details_when_postgres_is_unavailable(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(health_router, "is_database_ready", lambda: False)

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": 503,
        "detail": "The database connection is unavailable.",
        "instance": "/ready",
        "code": "database_unavailable",
        "request_id": response.headers[REQUEST_ID_HEADER],
    }
