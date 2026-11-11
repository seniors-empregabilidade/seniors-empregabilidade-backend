from pydantic import BaseModel, ConfigDict, Field, SecretStr


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(min_length=1, max_length=4096)
    access_token: SecretStr = Field(min_length=1, max_length=16384)
