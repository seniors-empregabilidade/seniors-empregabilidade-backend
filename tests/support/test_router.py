from collections.abc import Callable, Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings

CONTACT_PATH = "/api/v1/support/contact"


@pytest.fixture
def client_with(
    application: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Callable[..., TestClient]]:
    # A developer may have a real contact configured in their ignored .env.
    monkeypatch.delenv("SUPPORT_WHATSAPP_NUMBER", raising=False)
    monkeypatch.delenv("SUPPORT_WHATSAPP_MESSAGE", raising=False)

    def build(**settings: str) -> TestClient:
        application.dependency_overrides[get_settings] = lambda: (
            Settings.model_validate(settings)
        )
        return TestClient(application, raise_server_exceptions=False)

    yield build
    application.dependency_overrides.clear()


def test_returns_the_configured_contact_without_login(
    client_with: Callable[..., TestClient],
) -> None:
    client = client_with(
        support_whatsapp_number="5551999990000",
        support_whatsapp_message="Olá! Preciso de ajuda.",
    )

    response = client.get(CONTACT_PATH)

    assert response.status_code == 200
    assert response.json() == {
        "whatsapp_number": "5551999990000",
        "initial_message": "Olá! Preciso de ajuda.",
    }


def test_uses_the_default_message_when_only_the_number_is_set(
    client_with: Callable[..., TestClient],
) -> None:
    client = client_with(support_whatsapp_number="5551999990000")

    response = client.get(CONTACT_PATH)

    assert response.json()["initial_message"] == (
        "Olá! Preciso de ajuda com a plataforma Seniors."
    )


@pytest.mark.parametrize("settings", [{}, {"support_whatsapp_number": " "}])
def test_a_missing_contact_is_not_found(
    client_with: Callable[..., TestClient], settings: dict[str, str]
) -> None:
    response = client_with(**settings).get(CONTACT_PATH)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "support_contact_not_configured"
