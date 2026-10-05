"""Login / logout / current user / password change."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.security import audit
from app.security.rbac import (
    CSRF_COOKIE,
    SESSION_COOKIE,
    client_ip,
    current_user_allow_password_change,
)
from app.security.sessions import SessionInfo, create_session, revoke_session, revoke_user_sessions
from app.services import accounts_service, auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

PORTAL_ROLES = {"admin": {"admin"}, "staff": {"doctor", "nurse"}, "patient": {"patient"}}


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)
    portal: str | None = None  # "admin" | "staff" | "patient" — which login tab was used


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


def _set_cookies(response: Response, token: str, csrf: str) -> None:
    max_age = settings.session_absolute_hours * 3600
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", path="/")
    # Readable by page JS on purpose: it's echoed back in the X-CSRF-Token header.
    response.set_cookie(CSRF_COOKIE, csrf, max_age=max_age, httponly=False, secure=settings.cookie_secure,
                        samesite="strict", path="/")


def _me_payload(user: SessionInfo | dict) -> dict:
    u = user if isinstance(user, dict) else {
        "id": user.user_id, "username": user.username, "role": user.role, "patient_id": user.patient_id,
        "must_change_password": user.must_change_password,
    }
    details = accounts_service.get_user(u["id"])
    return {
        "id": u["id"], "username": u["username"], "role": u["role"], "patient_id": u["patient_id"],
        "display_name": details["display_name"] if details else None,
        "must_change_password": u["must_change_password"],
        "session_idle_minutes": settings.session_idle_minutes,
    }


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict:
    ip = client_ip(request)
    result = auth_service.authenticate(body.username, body.password, ip)
    if not result.ok:
        if result.error in ("locked", "rate_limited"):
            raise HTTPException(status_code=429, detail=(
                f"Too many failed attempts. Try again in {result.retry_after_minutes} minute(s)."))
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    user = result.user
    if body.portal and body.portal in PORTAL_ROLES and user["role"] not in PORTAL_ROLES[body.portal]:
        audit.record("login_wrong_portal", user_id=user["id"], username=user["username"], role=user["role"],
                     ip=ip, success=False, detail=body.portal)
        raise HTTPException(status_code=403, detail="This account cannot sign in through this portal.")

    token, csrf = create_session(user["id"], ip, request.headers.get("user-agent"))
    _set_cookies(response, token, csrf)
    return _me_payload(user)


@router.post("/logout")
def logout(request: Request, response: Response, user: SessionInfo = Depends(current_user_allow_password_change)) -> dict:
    revoke_session(request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    audit.record("logout", user_id=user.user_id, username=user.username, role=user.role, ip=client_ip(request))
    return {"ok": True}


@router.get("/me")
def me(user: SessionInfo = Depends(current_user_allow_password_change)) -> dict:
    return _me_payload(user)


@router.post("/change-password")
def change_password(body: ChangePasswordRequest, request: Request,
                    user: SessionInfo = Depends(current_user_allow_password_change)) -> dict:
    errors = auth_service.change_password(user.user_id, user.username, body.current_password, body.new_password)
    audit.record("password_change", user_id=user.user_id, username=user.username, role=user.role,
                 ip=client_ip(request), success=not errors)
    if errors:
        raise HTTPException(status_code=400, detail=" ".join(errors))
    revoke_user_sessions(user.user_id, keep_token_hash=user.token_hash)  # sign out other devices
    return {"ok": True}
