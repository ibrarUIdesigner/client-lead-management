import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        *,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        }
    }


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        errors = [
            {
                "loc": [str(part) for part in error.get("loc", [])],
                "msg": str(error.get("msg", "Invalid value.")),
                "type": str(error.get("type", "value_error")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=error_body(
                "VALIDATION_ERROR",
                "Request validation failed.",
                {"errors": errors},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = exc.detail if isinstance(exc.detail, str) else "Request failed."
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled_error request_id=%s error_type=%s",
            request_id,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "An unexpected error occurred."),
        )
