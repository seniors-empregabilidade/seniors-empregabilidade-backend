from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.errors import ProblemException
from app.db.session import is_database_ready

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={503: {"description": "Database is unavailable"}},
)
def readiness() -> HealthResponse:
    if not is_database_ready():
        raise ProblemException(
            status_code=503,
            title="Service Unavailable",
            code="database_unavailable",
            detail="The database connection is unavailable.",
        )
    return HealthResponse(status="ok")
