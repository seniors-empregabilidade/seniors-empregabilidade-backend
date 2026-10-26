from functools import lru_cache
from typing import Literal, Self

from pydantic import (
    AnyHttpUrl,
    Field,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    field_validator,
    model_validator,
)
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

    uploads_bucket: str = ""
    uploads_region: str = "us-east-2"
    # Only for a local S3-compatible server; production uses the instance role.
    s3_endpoint_url: AnyHttpUrl | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: SecretStr | None = None

    # Notification e-mails. `log` records that a message was produced and sends
    # nothing; `ses` needs a sender address verified in Amazon SES.
    email_backend: Literal["log", "ses"] = "log"
    email_sender_address: str = ""
    email_region: str = "us-east-2"
    # Public address of the web application, linked from every e-mail.
    app_public_url: AnyHttpUrl = AnyHttpUrl("http://localhost:5173")
    # Off by default so tests and one-off commands never start the loop.
    email_dispatch_enabled: bool = False
    email_dispatch_interval_seconds: PositiveFloat = 15.0
    email_max_attempts: PositiveInt = 5

    # Automatic applications (US-20): minimum compatibility, in percent, for the
    # platform to apply on a professional's behalf. The loop that re-evaluates
    # open jobs for newly registered professionals is off by default so tests
    # and one-off commands never start it.
    automatic_application_threshold_percent: int = Field(default=70, ge=1, le=100)
    automatic_application_enabled: bool = False
    automatic_application_interval_seconds: PositiveFloat = 86400.0

    # On in production, where CloudFront is in front and the socket address is
    # always the edge. Off locally, where the socket is the client.
    trust_proxy_headers: bool = False

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
        prefixes = []
        for item in value:
            normalized = item.strip().translate(str.maketrans("", "", "./-"))
            if not (
                normalized.isascii()
                and normalized.isdigit()
                and 1 <= len(normalized) <= 7
            ):
                raise ValueError("CNAE prefixes must contain 1 to 7 ASCII digits")
            prefixes.append(normalized)
        return prefixes

    @field_validator("personal_email_domains")
    @classmethod
    def retain_database_blocked_domains(cls, value: list[str]) -> list[str]:
        if not DATABASE_BLOCKED_EMAIL_DOMAINS.issubset(value):
            raise ValueError(
                "PERSONAL_EMAIL_DOMAINS must include the database-blocked domains"
            )
        return value

    @model_validator(mode="after")
    def require_ses_sender(self) -> Self:
        if self.email_backend == "ses" and not self.email_sender_address.strip():
            raise ValueError("EMAIL_SENDER_ADDRESS is required when EMAIL_BACKEND=ses")
        return self

    @property
    def app_public_url_value(self) -> str:
        return str(self.app_public_url).rstrip("/")

    @property
    def cors_origin_values(self) -> list[str]:
        return [str(origin).rstrip("/") for origin in self.cors_origins]


@lru_cache
def get_settings() -> Settings:
    return Settings()
