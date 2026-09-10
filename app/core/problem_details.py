from pydantic import BaseModel


class ProblemDetails(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    instance: str
    code: str
    request_id: str
    errors: dict[str, list[str]] | None = None


PROBLEM_RESPONSE = {
    "model": ProblemDetails,
    "content": {"application/problem+json": {}},
}
