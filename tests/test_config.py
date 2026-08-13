from pathlib import Path

import pytest
from pydantic import ValidationError

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
