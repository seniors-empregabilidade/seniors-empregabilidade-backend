import logging
from http import HTTPStatus
from typing import cast

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.middleware import REQUEST_ID_HEADER, get_request_id

_error_logger = logging.getLogger("app.error")


class ProblemException(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        title: str,
        code: str,
        detail: str,
        errors: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.title = title
        self.code = code
        self.detail = detail
        self.errors = errors


def _problem_response(
    request: Request,
    *,
    status_code: int,
    title: str,
    code: str,
    detail: str,
    errors: dict[str, list[str]] | None = None,
) -> JSONResponse:
    request_id = get_request_id() or "unavailable"
    content: dict[str, object] = {
        "type": "about:blank",
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "request_id": request_id,
    }
    if errors:
        content["errors"] = errors

    return JSONResponse(
        status_code=status_code,
        content=content,
        media_type="application/problem+json",
        headers={REQUEST_ID_HEADER: request_id},
    )


async def _handle_problem(request: Request, exc: Exception) -> JSONResponse:
    problem = cast(ProblemException, exc)
    return _problem_response(
        request,
        status_code=problem.status_code,
        title=problem.title,
        code=problem.code,
        detail=problem.detail,
        errors=problem.errors,
    )


async def _handle_validation(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    validation_error = cast(RequestValidationError, exc)
    errors: dict[str, list[str]] = {}
    for error in validation_error.errors():
        location = ".".join(str(part) for part in error["loc"])
        errors.setdefault(location, []).append(error["msg"])

    return _problem_response(
        request,
        status_code=422,
        title="Validation Error",
        code="validation_error",
        detail="The request contains invalid data.",
        errors=errors,
    )


async def _handle_http(request: Request, exc: Exception) -> JSONResponse:
    http_error = cast(StarletteHTTPException, exc)
    try:
        title = HTTPStatus(http_error.status_code).phrase
    except ValueError:
        title = "HTTP Error"

    detail = (
        http_error.detail
        if isinstance(http_error.detail, str)
        else "The request could not be completed."
    )
    return _problem_response(
        request,
        status_code=http_error.status_code,
        title=title,
        code=f"http_{http_error.status_code}",
        detail=detail,
    )


async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
    _error_logger.error(
        "unhandled_exception",
        extra={
            "event": "unhandled_exception",
            "request_id": get_request_id(),
            "exception_type": type(exc).__name__,
        },
    )
    return _problem_response(
        request,
        status_code=500,
        title="Internal Server Error",
        code="internal_error",
        detail="An unexpected error occurred.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ProblemException, _handle_problem)
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http)
    app.add_exception_handler(Exception, _handle_unexpected)
