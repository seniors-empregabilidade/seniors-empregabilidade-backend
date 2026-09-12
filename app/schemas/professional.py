from pydantic import BaseModel, EmailStr, Field
from datetime import date


class ProfessionalCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=1, description="Full name of the professional")
    cpf: str = Field(..., min_length=11, max_length=14, description="CPF (may contain punctuation)")
    date_of_birth: date = Field(..., description="Birth date (YYYY-MM-DD)")
    email: EmailStr = Field(..., description="Professional email address")
    password: str = Field(..., min_length=1, description="Plain password (will be hashed)")


class ProfessionalCreateResponse(BaseModel):
    id: int
    message: str = "Registration successful"
