"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_admin import router as admin_router
from app.api.routes_analysis import router as analysis_router
from app.api.routes_auth import router as auth_router
from app.api.routes_patients import router as patients_router
from app.api.routes_research import router as research_router
from app.config import settings
from app.models.registry import registry
from app.services.storage_service import encrypt_legacy_rows
from app.utils.logging_config import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load()
    encrypt_legacy_rows()
    yield


app = FastAPI(
    title=settings.api_title,
    description=(
        "Research/decision-support API for halo/double-ring fluid-pattern image analysis. "
        "NOT a diagnostic system. All patient endpoints require a signed-in session."
    ),
    version=settings.model_version,
    lifespan=lifespan,
)

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH"],
        allow_headers=["Content-Type", "X-CSRF-Token"],
    )

_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob:",
    "media-src 'self' blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])
# Swagger/ReDoc pull their UI from a CDN, so they get the other headers but not the CSP.
_DOCS_PATHS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(self), microphone=(), geolocation=()"
    h["Cross-Origin-Opener-Policy"] = "same-origin"
    if not request.url.path.startswith(_DOCS_PATHS):
        h["Content-Security-Policy"] = _CSP
    if request.url.path.startswith("/api/"):
        h["Cache-Control"] = "no-store"
    if settings.cookie_secure:
        h["Strict-Transport-Security"] = "max-age=31536000"
    return response


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(patients_router)
app.include_router(analysis_router)
app.include_router(research_router)

# The web app (login + role dashboards) is served at the root, so the whole system is one
# URL. Mounted last as a catch-all so it never shadows /api/* or /docs.
_web_dir = Path(__file__).resolve().parent.parent.parent / "web_app"
if _web_dir.is_dir():
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="web_app")
