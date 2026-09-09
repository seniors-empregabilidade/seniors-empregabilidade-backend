from pydantic import BaseModel, ConfigDict, Field


class SendVerificationCodeRequest(BaseModel):
    """Address that should receive a verification code.

    The bounds mirror `app_user.email`. No email format is enforced: answering
    422 for a malformed address while accepting every other one would make the
    response depend on the input, and this operation is deliberately identical
    for a registered address, an unregistered one, and an unusable one.
    """

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"email": "candidate@example.invalid"}},
    )

    email: str = Field(min_length=1, max_length=150)
