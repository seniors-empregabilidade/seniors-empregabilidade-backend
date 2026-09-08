from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class LoginRequest(BaseModel):
    """Credentials submitted to the sign-in endpoint.

    The email bounds mirror `app_user.email`. No email format or password policy
    is enforced here: rejecting a malformed value with 422 while rejecting a
    well-formed one with 401 would tell an attacker which inputs are worth trying.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "email": "candidate@example.invalid",
                "password": "LocalDemoOnly!2026",
            }
        },
    )

    email: str = Field(
        min_length=3,
        max_length=150,
        description="Registered email address, compared in lowercase.",
    )
    password: SecretStr = Field(
        min_length=1,
        max_length=256,
        description="Account password. Never logged and never returned.",
    )

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("email must not be blank")
        return normalized
