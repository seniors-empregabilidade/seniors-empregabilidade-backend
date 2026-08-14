from typing import Annotated

from fastapi import FastAPI, Path
from fastapi.testclient import TestClient

from app.core.errors import ProblemException
from app.core.middleware import REQUEST_ID_HEADER


def test_not_found_uses_problem_details(client: TestClient) -> None:
    response = client.get("/missing")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "http_404"
    assert response.json()["instance"] == "/missing"
    assert response.json()["request_id"] == response.headers[REQUEST_ID_HEADER]


def test_validation_errors_do_not_echo_input(
    application: FastAPI,
    client: TestClient,
) -> None:
    @application.get("/_test/validation/{value}", include_in_schema=False)
    def validation_route(value: Annotated[int, Path(ge=1)]) -> dict[str, int]:
        return {"value": value}

    response = client.get("/_test/validation/not-an-integer")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert "path.value" in body["errors"]
    assert "input" not in body


def test_explicit_application_problem_is_serialized(
    application: FastAPI,
    client: TestClient,
) -> None:
    @application.get("/_test/conflict", include_in_schema=False)
    def conflict_route() -> None:
        raise ProblemException(
            status_code=409,
            title="Conflict",
            code="test_conflict",
            detail="The test operation conflicts with current state.",
        )

    response = client.get("/_test/conflict")

    assert response.status_code == 409
    assert response.json()["code"] == "test_conflict"


def test_unexpected_errors_return_a_safe_problem(
    application: FastAPI,
    client: TestClient,
) -> None:
    @application.get("/_test/failure", include_in_schema=False)
    def failure_route() -> None:
        raise RuntimeError("private implementation detail")

    response = client.get("/_test/failure")

    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert "private implementation detail" not in response.text
