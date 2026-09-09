from pydantic import BaseModel, ConfigDict, Field


class ConfirmVerificationCodeRequest(BaseModel):
    """A verification code submitted for an address.

    The email bounds mirror `app_user.email` and no format is enforced, for the
    same reason as the send operation. The code bounds are permissive because the
    provider owns the code format and decides what is valid; rejecting a length
    here would only reveal what the provider issues.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {"email": "candidate@example.invalid", "code": "123456"}
        },
    )

    email: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=64)
