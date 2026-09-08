from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from app.core.config import DEFAULT_DATABASE_URL, Settings


def test_settings_use_safe_local_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)

    settings = Settings()

    assert settings.database_url == DEFAULT_DATABASE_URL
    assert settings.cors_origin_values == ["http://localhost:5173"]
    assert settings.app_env == "local"


def test_settings_parse_cors_origins_from_environment(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(
        "CORS_ORIGINS",
        '["https://app.example.com/", "http://localhost:5173"]',
    )

    settings = Settings()

    assert settings.cors_origin_values == [
        "https://app.example.com",
        "http://localhost:5173",
    ]


def test_settings_reject_a_non_psycopg_database_url(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValidationError, match="postgresql\\+psycopg"):
        Settings(database_url="sqlite:///local.db")


def test_the_cognito_client_secret_is_not_printable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)

    settings = Settings(cognito_client_secret=SecretStr("super-secret-value"))

    assert "super-secret-value" not in repr(settings)
    assert settings.cognito_client_secret is not None
    assert settings.cognito_client_secret.get_secret_value() == "super-secret-value"
