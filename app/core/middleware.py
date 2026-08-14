import logging
import re
from contextvars import ContextVar, Token
from time import perf_counter
from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-ID"
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
_request_logger = logging.getLogger("app.request")


def get_request_id() -> str | None:
    return _request_id_context.get()


def normalize_request_id(value: str | None) -> str:
    if value is not None and _REQUEST_ID_PATTERN.fullmatch(value):
        return value
    return str(uuid4())


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = normalize_request_id(headers.get(REQUEST_ID_HEADER))
        token = _request_id_context.set(request_id)
        start_time = perf_counter()
        status_code = 500

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                if response_headers.get(REQUEST_ID_HEADER) is None:
                    response_headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            self._log_request(scope, status_code, request_id, start_time)
            self._reset_context(token)

    @staticmethod
    def _log_request(
        scope: Scope,
        status_code: int,
        request_id: str,
        start_time: float,
    ) -> None:
        route = scope.get("route")
        path = getattr(route, "path", scope["path"])
        if path in {"/health", "/ready"}:
            return

        log = _request_logger.info
        if status_code >= 500:
            log = _request_logger.error
        elif status_code >= 400:
            log = _request_logger.warning

        log(
            "request_completed",
            extra={
                "event": "request_completed",
                "request_id": request_id,
                "method": scope["method"],
                "path": path,
                "status_code": status_code,
                "duration_ms": round((perf_counter() - start_time) * 1000, 2),
            },
        )

    @staticmethod
    def _reset_context(token: Token[str | None]) -> None:
        _request_id_context.reset(token)
