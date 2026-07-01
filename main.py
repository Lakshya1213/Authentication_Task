"""
FastAPI application entry point.

Wires configuration, middleware, database init, logging, and route registration.
"""

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from config import get_settings
from db.database import init_db
from routes.auth import router as auth_router
from routes.calendar import router as calendar_router
from routes.mail import router as mail_router
from routes.crm import router as crm_router
from schemas.auth_schema import ErrorResponse
from transcript_agent.routes import router as transcript_router

settings = get_settings()
STATIC_DIR = Path(__file__).resolve().parent / "static"


def configure_logging() -> None:
    """Configure structured application logging to stdout."""
    logging.basicConfig(
        level=logging.DEBUG if settings.debug else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="POC 1: Google OAuth authentication and authorization only.",
    version="1.0.0",
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    session_cookie="oauth_poc_session",
    max_age=60 * 60 * 24 * 7,  # 7 days
    https_only=False,
    same_site="lax",
)

app.include_router(auth_router)
app.include_router(calendar_router)
app.include_router(mail_router)
app.include_router(crm_router)
app.include_router(transcript_router)

if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    """Serve the single-page frontend."""
    return FileResponse(STATIC_DIR / "index.html")


@app.on_event("startup")
def on_startup() -> None:
    logger.info("Starting %s", settings.app_name)
    init_db()


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.warning("Validation error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error_type="validation_error",
            message="Invalid request parameters",
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error_type="internal_error",
            message="An unexpected error occurred",
        ).model_dump(),
    )
