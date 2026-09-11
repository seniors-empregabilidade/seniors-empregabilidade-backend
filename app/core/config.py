from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, PositiveFloat, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_DATABASE_URL = (
    "postgresql+psycopg://seniors:seniors_local@localhost:5432/seniors_empregabilidade"
)
DATABASE_BLOCKED_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "hotmail.com",
        "outlook.com",
        "yahoo.com",
        "icloud.com",
        "bol.com.br",
        "uol.com.br",
    }
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_env: Literal["local", "test", "staging", "production"] = "local"
    database_url: str = DEFAULT_DATABASE_URL
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[AnyHttpUrl] = Field(
        default_factory=lambda: [AnyHttpUrl("http://localhost:5173")]
    )
    brasil_api_base_url: AnyHttpUrl = AnyHttpUrl("https://brasilapi.com.br/api")
    brasil_api_timeout_seconds: PositiveFloat = 5.0
    blocked_cnae_prefixes: list[str] = Field(default_factory=list)
    personal_email_domains: list[str] = Field(
        default_factory=lambda: [
            "gmail.com",
            "hotmail.com",
            "outlook.com",
            "yahoo.com",
            "icloud.com",
            "bol.com.br",
            "uol.com.br",
        ]
    )

    cognito_region: str = "us-east-2"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    cognito_client_secret: SecretStr | None = None

    @field_validator("database_url")
    @classmethod
    def require_psycopg_driver(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("DATABASE_URL must use the postgresql+psycopg driver")
        return value

    @field_validator("personal_email_domains")
    @classmethod
    def normalize_string_lists(cls, value: list[str]) -> list[str]:
        return [item.strip().lower() for item in value if item.strip()]

    @field_validator("blocked_cnae_prefixes")
    @classmethod
    def normalize_cnae_prefixes(cls, value: list[str]) -> list[str]:
        return [
            normalized
            for item in value
            if (
                normalized := "".join(
                    character for character in item if character.isdigit()
                )
            )
        ]

    @field_validator("personal_email_domains")
    @classmethod
    def retain_database_blocked_domains(cls, value: list[str]) -> list[str]:
        if not DATABASE_BLOCKED_EMAIL_DOMAINS.issubset(value):
            raise ValueError(
                "PERSONAL_EMAIL_DOMAINS must include the database-blocked domains"
            )
        return value

    @property
    def cors_origin_values(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]


@lru_cache
def get_settings() -> Settings:
    return Settings()
