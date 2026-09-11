from uuid import UUID

from pydantic import BaseModel, Field

from app.db.models.enums import UserType


class LoginResponse(BaseModel):
    access_token: str = Field(repr=False)
    id_token: str = Field(repr=False)
    refresh_token: str | None = Field(repr=False)
    expires_in: int
    token_type: str
    user_id: UUID
    user_type: UserType
