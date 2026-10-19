from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

_TOO_LARGE = "The request body is too large."


# Raised from `receive`, so it stops FastAPI's body parsing before a file reaches
# disk; FastAPI re-raises HTTPException there and the app answers with a problem.
class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length", "")
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            if declared.isdigit() and int(declared) > self.max_bytes:
                raise HTTPException(status_code=413, detail=_TOO_LARGE)
            message = await receive()
            if message["type"] == "http.request":
                # Counts real bytes too: Content-Length may be absent or false.
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    raise HTTPException(status_code=413, detail=_TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)
