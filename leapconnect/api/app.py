"""FastAPI application factory and lifespan wiring."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from leapmotor_api.exceptions import LeapmotorApiError

from leapconnect import config
from leapconnect.api.deps import PUBLIC_PATHS, SESSION_COOKIE_NAME
from leapconnect.api.routers import (
    charging,
    commands,
    connection,
    history,
    identity,
    maintenance,
    notifications,
    system,
    trips,
    vehicles,
    zones,
)
from leapconnect.config import FRONTEND_DIST
from leapconnect.container import container

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await container.startup()
    yield
    await container.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(title="Leapmotor Dashboard", lifespan=lifespan)

    # CORS — Vue dev server by default, overridable via CORS_ORIGINS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(LeapmotorApiError)
    async def leapmotor_api_error_handler(request: Request, exc: LeapmotorApiError):
        """Return a proper JSON 502 response for any unhandled LeapmotorApiError."""
        _LOGGER.warning(
            "LeapmotorApiError on %s %s: %s", request.method, request.url.path, exc
        )
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.middleware("http")
    async def session_middleware(request: Request, call_next):
        """Require a valid session cookie for all /api/ routes except public ones."""
        path = request.url.path
        if path.startswith("/api/") and path not in PUBLIC_PATHS:
            token = request.cookies.get(SESSION_COOKIE_NAME)
            if not container.sessions.validate(token):
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Authentication required"},
                )
        return await call_next(request)

    # Serve Vue SPA in production (built files in frontend/dist)
    if FRONTEND_DIST.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_DIST / "assets")),
            name="assets",
        )

    # Routers — one per bounded context. Order matters only for the SPA
    # fallback, which must be registered last.
    app.include_router(identity.router)
    app.include_router(connection.router)
    app.include_router(vehicles.router)
    app.include_router(history.router)
    app.include_router(commands.router)
    app.include_router(trips.router)
    app.include_router(charging.router)
    app.include_router(maintenance.router)
    app.include_router(notifications.router)
    app.include_router(zones.router)
    app.include_router(system.router)

    # SPA fallback — must be last
    if FRONTEND_DIST.is_dir():

        @app.get("/{path:path}")
        async def serve_spa_fallback(path: str):
            """Serve Vue SPA for any non-API route (client-side routing)."""
            file = FRONTEND_DIST / path
            if file.is_file():
                return FileResponse(str(file))
            return FileResponse(str(FRONTEND_DIST / "index.html"))

    return app


app = create_app()
