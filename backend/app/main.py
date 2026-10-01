"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes_analysis import router as analysis_router
from app.api.routes_research import router as research_router
from app.config import settings
from app.models.registry import registry
from app.utils.logging_config import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load()
    yield


app = FastAPI(
    title=settings.api_title,
    description=(
        "Research/decision-support API for halo/double-ring fluid-pattern image analysis. "
        "NOT a diagnostic system. See /api/health and /api/model-info."
    ),
    version=settings.model_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before any real deployment
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis_router)
app.include_router(research_router)

# Lightweight web demo frontend (web_demo/index.html) — stands in for the unverified
# Flutter app (no SDK in this environment) so the pipeline can be exercised from a
# browser without one. Mounted last so it never shadows the /api/* routes above.
_web_demo_dir = Path(__file__).resolve().parent.parent.parent / "web_demo"
if _web_demo_dir.is_dir():
    app.mount("/demo", StaticFiles(directory=_web_demo_dir, html=True), name="demo")
