import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import Response

from app.api.v1.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging
from app.db.session import create_db_engine, create_session_factory
from app.jobs.discovery import start_discovery_scheduler
from app.jobs.gmail_sync import start_gmail_scheduler

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "request_completed method=%s path=%s status=%s duration_ms=%.1f request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
        response.headers["X-Request-ID"] = request_id
        return response


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    discovery_scheduler = None
    gmail_scheduler = None
    settings = app.state.settings
    if settings.app_env != "test":
        if settings.discovery_enabled:
            discovery_scheduler = start_discovery_scheduler(app)
            app.state.discovery_scheduler = discovery_scheduler
        if settings.gmail_sync_enabled:
            gmail_scheduler = start_gmail_scheduler(app)
            app.state.gmail_scheduler = gmail_scheduler
    yield
    if discovery_scheduler is not None:
        discovery_scheduler.shutdown(wait=False)
    if gmail_scheduler is not None:
        gmail_scheduler.shutdown(wait=False)
    app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Client Acquisition Tool", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = create_db_engine(settings.database_url)
    app.state.session_factory = create_session_factory(app.state.engine)

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
