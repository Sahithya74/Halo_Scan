"""Authentication + role checks as FastAPI dependencies.

Every request carrying a session cookie is checked for:
  - a live, unexpired server-side session,
  - a matching CSRF token on state-changing methods (double-submit cookie pattern),
  - a role allowed for the endpoint,
  - no pending forced password change (except on the endpoints that resolve it).
"""
from __future__ import annotations

import hmac
from typing import Callable

from fastapi import Depends, HTTPException, Request

from app.security.sessions import SessionInfo, get_session

SESSION_COOKIE = "halo_session"
CSRF_COOKIE = "halo_csrf"
CSRF_HEADER = "X-CSRF-Token"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

STAFF_ROLES = ("doctor", "nurse")


def client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _authenticated(request: Request) -> SessionInfo:
    session = get_session(request.cookies.get(SESSION_COOKIE))
    if session is None:
        raise HTTPException(status_code=401, detail="Not signed in or session expired.")
    if request.method in _UNSAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, session.csrf_token):
            raise HTTPException(status_code=403, detail="Missing or invalid CSRF token.")
    return session


def current_user_allow_password_change(request: Request) -> SessionInfo:
    """For /auth/me, /auth/logout and /auth/change-password only."""
    return _authenticated(request)


def current_user(request: Request) -> SessionInfo:
    session = _authenticated(request)
    if session.must_change_password:
        raise HTTPException(status_code=403, detail="password_change_required")
    return session


def require_roles(*roles: str) -> Callable[..., SessionInfo]:
    def dependency(user: SessionInfo = Depends(current_user)) -> SessionInfo:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Your role cannot access this resource.")
        return user
    return dependency
