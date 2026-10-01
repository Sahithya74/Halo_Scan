"""Shared FastAPI dependencies. Currently just the research-mode API key check."""
from __future__ import annotations

import logging

from fastapi import HTTPException, Security
from fastapi.security import APIKeyHeader

from app.config import settings

logger = logging.getLogger(__name__)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
_warned_open = False


def require_research_api_key(provided_key: str | None = Security(_api_key_header)) -> None:
    global _warned_open
    if not settings.research_api_key:
        if not _warned_open:
            logger.warning(
                "HALO_RESEARCH_API_KEY is not set — /api/research/* endpoints are "
                "UNAUTHENTICATED. Fine for local development; set the env var before "
                "exposing this service beyond localhost."
            )
            _warned_open = True
        return
    if provided_key != settings.research_api_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
