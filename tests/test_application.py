import pytest
from fastapi.testclient import TestClient

from app.core.middleware import REQUEST_ID_HEADER


def test_openapi_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"] == {
        "title": "Seniors - Empregabilidade API",
        "version": "0.1.0",
    }


def test_valid_incoming_request_id_is_preserved(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "request_123.test"},
    )

    assert response.headers[REQUEST_ID_HEADER] == "request_123.test"


def test_invalid_incoming_request_id_is_replaced(client: TestClient) -> None:
    response = client.get(
        "/health",
        headers={REQUEST_ID_HEADER: "invalid request id with spaces"},
    )

    assert response.headers[REQUEST_ID_HEADER] != "invalid request id with spaces"


def test_local_frontend_origin_is_allowed(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ("http://localhost:5173")
    assert response.headers.get("access-control-allow-credentials") is None


def test_unconfigured_origin_is_not_allowed(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.parametrize("path", ["/health", "/ready"])
def test_health_routes_are_outside_api_version_prefix(
    client: TestClient,
    path: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if path == "/ready":
        monkeypatch.setattr(
            "app.health.router.is_database_ready",
            lambda: True,
        )

    assert client.get(path).status_code == 200
    assert client.get(f"/api/v1{path}").status_code == 404
