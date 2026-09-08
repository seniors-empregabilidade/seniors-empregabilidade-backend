from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import UserType


class LoginResponse(BaseModel):
    """The session established by a successful sign-in.

    Carries the provider tokens plus the caller's own identifier and role.
    The Cognito `sub` claim is not this identifier, so `user_id` is the only way
    for a client to address the account in this API.
    """

    access_token: str = Field(description="Provider access token.")
    id_token: str = Field(description="Provider identity token.")
    refresh_token: str | None = Field(
        default=None, description="Provider refresh token, when the client issues one."
    )
    expires_in: int = Field(description="Access token lifetime in seconds.")
    token_type: str = Field(description="Authorization scheme for the access token.")
    user_id: UUID = Field(description="Identifier of the account in this API.")
    user_type: UserType = Field(description="Role granted to the account.")
