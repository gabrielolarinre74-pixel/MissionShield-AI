"""
MissionShield AI — FastAPI application factory.

Registers all routers, configures CORS, and sets up structured
exception handling. Does not import or expose any secret values.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.exceptions import DataSourceUnavailableError, MissionShieldError
from app.routes import health, space_weather

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("MissionShield API v%s starting up", settings.APP_VERSION)
    logger.info("Frontend origin: %s", settings.FRONTEND_ORIGIN)
    # Intentionally not logging NASA_API_KEY or watsonx credentials.
    yield
    logger.info("MissionShield API shutting down")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "MissionShield AI — space mission decision-support platform. "
            "IBM AI Builders Challenge, August 2026."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # CORS — allow the configured frontend origin.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # Structured error handlers — never expose stack traces or credentials.
    @app.exception_handler(DataSourceUnavailableError)
    async def handle_source_unavailable(
        request: Request, exc: DataSourceUnavailableError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATA_SOURCE_UNAVAILABLE",
                "message": f"Data source unavailable: {exc.source}",
            },
        )

    @app.exception_handler(MissionShieldError)
    async def handle_domain_error(
        request: Request, exc: MissionShieldError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={"error": "INTERNAL_ERROR", "message": "An internal error occurred."},
        )

    # Register routers.
    app.include_router(health.router, prefix="/api")
    app.include_router(space_weather.router, prefix="/api")

    return app


app = create_app()
