import logging
from uuid import UUID

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.auth.dependencies import require_approved_company
from app.auth.schemas.current_user import CurrentUser
from app.companies.router import get_company_registry
from app.core.config import get_settings
from app.core.rate_limit import client_identifier, limiter
from app.db.models.enums import CompanyStatus, UserType
from app.db.session import get_session
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


_PROFESSIONAL = {
    "full_name": "Synthetic Person",
    "cpf": "111.444.777-35",
    "birth_date": "1970-01-01",
    "phone": "+55 51 99999-9999",
    "email": "person@example.com",
    "password": "LocalDemoOnly!2026",
    "terms_version_accepted": "v1",
    "city": "Porto Alegre",
    "state": "RS",
}
_COMPANY = {
    "cnpj": "11222333000181",
    "display_name": "Synthetic Company",
    "address": {
        "street": "Synthetic Street",
        "number": "1",
        "neighborhood": "Test",
        "city": "Test",
        "state": "RS",
        "zip_code": "90000000",
    },
    "corporate_email": "registration@company.example.invalid",
    "password": "SyntheticPass!2026",
    "terms_accepted": True,
    "terms_version": "v1",
}
_CONTACT = {
    "job_id": "11111111-1111-4111-8111-111111111111",
    "candidate_id": "22222222-2222-4222-8222-222222222222",
    "message": "Synthetic message",
}
_REFRESH = {"refresh_token": "synthetic-refresh", "access_token": "synthetic-access"}


@pytest.mark.parametrize(
    ("path", "payload", "allowed"),
    [
        ("/api/v1/professionals", _PROFESSIONAL, 5),
        ("/api/v1/companies", _COMPANY, 5),
        ("/api/v1/contacts", _CONTACT, 10),
        ("/api/v1/auth/refresh", _REFRESH, 60),
    ],
)
def test_email_sending_and_session_routes_are_limited_per_origin(
    application: FastAPI,
    client: TestClient,
    path: str,
    payload: dict[str, object],
    allowed: int,
) -> None:
    # The limit runs before the handler body, so a session that fails on use is
    # enough: the allowed calls end in 500 and only the next one must be 429.
    application.dependency_overrides[get_session] = object
    application.dependency_overrides[get_identity_provider] = FakeIdentityProvider
    application.dependency_overrides[get_company_registry] = object
    application.dependency_overrides[require_approved_company] = lambda: CurrentUser(
        id=UUID("33333333-3333-4333-8333-333333333333"),
        user_type=UserType.COMPANY,
        company_status=CompanyStatus.APPROVED,
    )

    statuses = [client.post(path, json=payload).status_code for _ in range(allowed)]
    refused = client.post(path, json=payload)

    assert 429 not in statuses
    assert refused.status_code == 429
    assert refused.json()["code"] == "rate_limited"
    application.dependency_overrides.clear()
