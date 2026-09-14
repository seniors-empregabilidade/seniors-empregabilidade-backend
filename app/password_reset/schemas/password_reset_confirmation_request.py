from pydantic import Field, SecretStr

from app.password_reset.schemas.password_reset_request import PasswordResetRequest


class PasswordResetConfirmationRequest(PasswordResetRequest):
    code: SecretStr = Field(min_length=1, max_length=2048)
    # The provider owns the password policy; a local copy would drift from it.
    password: SecretStr = Field(min_length=1, max_length=256)
