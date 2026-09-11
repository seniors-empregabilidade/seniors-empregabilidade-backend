from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class EmailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=150, pattern=r"^[^\s@]+@[^\s@]+$")

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        return value.strip().lower() if isinstance(value, str) else value


class EmailConfirmationRequest(EmailRequest):
    code: SecretStr = Field(min_length=1, max_length=2048)
