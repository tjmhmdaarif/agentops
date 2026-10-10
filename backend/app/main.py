"""FastAPI application factory + entrypoint.

Serves the REST API, the SSE stream, and (in production) the built React app.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api import (
    routes_analytics,
    routes_auth,
    routes_devices,
    routes_events,
    routes_incidents,
    routes_simulation,
    routes_telemetry,
)
from app.core.auth import SESSION_COOKIE
from app.core.config import Settings
from app.core.logging import configure_logging, get_logger
from app.core.runtime import AgentOpsRuntime
from app.db.schemas import ConfigOut, HealthOut

log = get_logger("main")


def build_app(settings: Settings | None = None) -> FastAPI:
    configure_logging()
    settings = settings or Settings.from_env()
    runtime = AgentOpsRuntime(settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        runtime.init_db()
        if settings.simulation_enabled and settings.simulation_autostart:
            runtime.engine.start()
        runtime.start_background()
        log.info("agentops_started env=%s devices=%d llm=%s",
                 settings.app_env, len(runtime.engine.devices),
                 "enabled" if runtime.llm.available else "disabled")
        yield
        runtime.engine.stop()
        await runtime.stop_background()
        log.info("agentops_stopped")

    app = FastAPI(title="AgentOps 2.0", version="2.0.0", lifespan=lifespan)
    app.state.runtime = runtime
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

    AUTH_PUBLIC = ("/api/health", "/api/auth/login", "/api/auth/public-config")

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        """Session-cookie gate for the whole API (health + login stay public)."""
        path = request.url.path
        if path.startswith("/api/") and path not in AUTH_PUBLIC:
            username = runtime.auth.resolve(request.cookies.get(SESSION_COOKIE))
            if username is None:
                return JSONResponse(
                    status_code=401,
                    content={"error": {"type": "unauthenticated", "message": "Sign in required"}},
                )
            request.state.username = username
        return await call_next(request)

    for r in (routes_auth, routes_devices, routes_telemetry, routes_incidents,
              routes_simulation, routes_analytics, routes_events):
        app.include_router(r.router)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled_error path=%s", request.url.path)
        # Only expose internal error detail outside production — in prod, leaking
        # exception text can disclose SQL, paths, or internals to clients.
        detail = str(exc) if settings.app_env != "production" else "Internal server error"
        return JSONResponse(status_code=500, content={
            "error": {"type": type(exc).__name__, "message": detail}
        })

    @app.get("/api/health", response_model=HealthOut)
    def health() -> dict:
        return runtime.health()

    @app.get("/api/config", response_model=ConfigOut)
    def config() -> dict:
        return {
            "app_env": settings.app_env,
            "llm_enabled": settings.llm_enabled,
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "anomaly_threshold": settings.anomaly_threshold,
            "anomaly_persistence": settings.anomaly_persistence,
            "incident_cooldown_seconds": settings.incident_cooldown_seconds,
            "simulation_speed": runtime.engine.speed,
            "device_count": len(runtime.engine.devices),
            "feature_flags": settings.feature_flags,
            "show_demo_creds": settings.show_demo_creds,
            "demo_username": settings.admin_username if settings.show_demo_creds else "",
            "demo_password": settings.admin_password if settings.show_demo_creds else "",
        }

    @app.get("/api/auth/public-config")
    def auth_public_config() -> dict:
        """Login-page metadata — intentionally public (no secrets beyond demo mode)."""
        return {
            "product": "AgentOps 2.0",
            "show_demo_creds": settings.show_demo_creds,
            "demo_username": settings.admin_username if settings.show_demo_creds else "",
            "demo_password": settings.admin_password if settings.show_demo_creds else "",
        }

    # ------------------------------------------------ static frontend (production)
    static_dir = Path(settings.static_dir)
    if static_dir.is_dir():
        assets = static_dir / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """Client-side routing fallback: any non-API path gets index.html."""
            from fastapi.responses import FileResponse

            if full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": {"type": "not_found", "message": full_path}})
            candidate = static_dir / full_path
            if full_path and candidate.is_file() and candidate.is_relative_to(static_dir):
                return FileResponse(candidate)
            index = static_dir / "index.html"
            if not index.is_file():  # e.g. frontend mid-rebuild — never crash
                return JSONResponse(status_code=503, content={"error": {"type": "frontend_unavailable"}})
            return FileResponse(index)

        log.info("serving_frontend dir=%s", static_dir)

    return app


app = build_app()


def main() -> None:  # pragma: no cover
    import uvicorn

    settings = Settings.from_env()
    uvicorn.run("app.main:app", host=settings.host, port=settings.port,
                reload=settings.app_env == "development")


if __name__ == "__main__":  # pragma: no cover
    main()
