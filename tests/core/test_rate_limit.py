import logging

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.core.rate_limit import client_identifier, limiter
from app.identity.dependencies import get_identity_provider
from tests.identity.fakes import FakeIdentityProvider


def _request(headers: dict[str, str], client_host: str = "203.0.113.9") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/login",
            "headers": raw,
            "client": (client_host, 1234),
            "query_string": b"",
        }
    )


def test_the_viewer_address_is_the_last_forwarded_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # A client controls the start of X-Forwarded-For; CloudFront appends the
    # real address at the end. Reading the first entry would be forgeable.
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    forged = "1.1.1.1, 2.2.2.2, 198.51.100.7"
    assert client_identifier(_request({"x-forwarded-for": forged})) == "198.51.100.7"

    get_settings.cache_clear()


def test_a_missing_forwarded_header_is_logged_as_an_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "true")
    get_settings.cache_clear()

    with caplog.at_level(logging.ERROR, logger="app.rate_limit"):
        identifier = client_identifier(_request({}))

    assert identifier == "203.0.113.9"
    assert "x_forwarded_for_missing" in caplog.text

    get_settings.cache_clear()


def test_without_a_proxy_the_socket_address_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TRUST_PROXY_HEADERS", "false")
    get_settings.cache_clear()

    # The header is ignored even when present: with no proxy in front, trusting
    # it would let any client pick its own key.
    assert client_identifier(_request({"x-forwarded-for": "9.9.9.9"})) == "203.0.113.9"

    get_settings.cache_clear()


def test_the_sixth_consecutive_call_is_refused_with_problem_details(
    application: FastAPI, client: TestClient
) -> None:
    # Without a provider the dependency fails with 503 before the endpoint, and
    # the limiter, which runs inside the endpoint, would never be exercised.
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider

    limiter.reset()
    path = "/api/v1/password-reset/send"
    payload = {"email": "person@example.invalid"}

    responses = [client.post(path, json=payload) for _ in range(6)]
    assert [r.status_code for r in responses[:5]] == [202] * 5

    refused = responses[-1]
    assert refused.status_code == 429
    body = refused.json()
    assert body["code"] == "rate_limited"
    assert body["status"] == 429
    assert body["instance"] == path

    limiter.reset()
