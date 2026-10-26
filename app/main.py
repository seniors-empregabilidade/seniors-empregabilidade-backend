from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.candidates.domain.certificate_document import MAX_DOCUMENT_BYTES
from app.core.body_limit import RequestBodyLimitMiddleware
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import REQUEST_ID_HEADER, RequestContextMiddleware
from app.core.rate_limit import limiter
from app.db.session import dispose_engine
from app.health.router import router as health_router
from app.notifications.email_dispatcher import build_email_dispatcher


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    settings: Settings = application.state.settings
    dispatcher = (
        build_email_dispatcher(settings) if settings.email_dispatch_enabled else None
    )
    if dispatcher is not None:
        dispatcher.start()
    yield
    if dispatcher is not None:
        dispatcher.stop()
    dispose_engine()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    # Interactive docs stay closed in production: less scanner noise, and the
    # contract is already public through the repository.
    docs_enabled = resolved_settings.app_env != "production"

    application = FastAPI(
        title="Seniors - Empregabilidade API",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.state.limiter = limiter
    application.state.settings = resolved_settings
    register_exception_handlers(application)

    # The largest body is one certificate upload plus its multipart framing.
    application.add_middleware(
        RequestBodyLimitMiddleware, max_bytes=MAX_DOCUMENT_BYTES + 64 * 1024
    )
    application.add_middleware(RequestContextMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_values,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
        # The frontend reads the CSV export's file name from Content-Disposition.
        expose_headers=[REQUEST_ID_HEADER, "Content-Disposition"],
    )

    application.include_router(health_router)
    application.include_router(api_router, prefix="/api/v1")
    return application


app = create_app()
