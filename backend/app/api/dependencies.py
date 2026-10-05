"""Shared FastAPI dependencies for the research-mode endpoints."""
from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, Security
from fastapi.security import APIKeyHeader

from app.config import settings
from app.security.rbac import current_user

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_research_api_key(request: Request, provided_key: str | None = Security(_api_key_header)) -> None:
    """Admin session, or — for headless scripts — a matching X-API-Key when one is configured."""
    if settings.research_api_key and provided_key and hmac.compare_digest(provided_key, settings.research_api_key):
        return
    if provided_key:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header.")
    user = current_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Research mode is restricted to administrators.")
