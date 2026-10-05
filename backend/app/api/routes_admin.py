"""Administrator endpoints: staff accounts, audit log, system stats."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.models.registry import registry
from app.security import audit
from app.security.passwords import generate_temporary_password
from app.security.rbac import client_ip, require_roles
from app.security.sessions import SessionInfo
from app.services import accounts_service, storage_service
from app.services.analysis_service import model_card

router = APIRouter(prefix="/api/admin", tags=["admin"])
admin_only = require_roles("admin")


class CreateUserRequest(BaseModel):
    username: str = Field(max_length=32)
    role: str
    display_name: str = Field(max_length=120)


class UpdateUserRequest(BaseModel):
    active: bool | None = None
    reset_password: bool = False


@router.get("/users")
def list_users(user: SessionInfo = Depends(admin_only)) -> list[dict]:
    return [u for u in accounts_service.list_users() if u["role"] != "patient"]


@router.post("/users")
def create_user(body: CreateUserRequest, request: Request, user: SessionInfo = Depends(admin_only)) -> dict:
    if body.role not in ("admin", "doctor", "nurse"):
        raise HTTPException(status_code=400, detail="Admins create admin, doctor or nurse accounts. "
                                                    "Patients are registered by doctors/nurses.")
    temp = generate_temporary_password()
    try:
        new_id = accounts_service.create_user(body.username, temp, body.role, body.display_name,
                                              created_by=user.user_id, must_change_password=True)
    except accounts_service.AccountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit.record("user_create", user_id=user.user_id, username=user.username, role=user.role,
                 target=f"user:{new_id}", ip=client_ip(request), detail=body.role)
    return {"user": accounts_service.get_user(new_id), "temporary_password": temp}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UpdateUserRequest, request: Request,
                user: SessionInfo = Depends(admin_only)) -> dict:
    target = accounts_service.get_user(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found.")
    response: dict = {}
    if body.active is not None:
        if not body.active and target["role"] == "admin" and accounts_service.count_admins() <= 1:
            raise HTTPException(status_code=400, detail="Cannot deactivate the last active administrator.")
        if not body.active and user_id == user.user_id:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account.")
        accounts_service.set_active(user_id, body.active)
        audit.record("user_activate" if body.active else "user_deactivate", user_id=user.user_id,
                     username=user.username, role=user.role, target=f"user:{user_id}", ip=client_ip(request))
    if body.reset_password:
        response["temporary_password"] = accounts_service.reset_password(user_id)
        audit.record("user_password_reset", user_id=user.user_id, username=user.username, role=user.role,
                     target=f"user:{user_id}", ip=client_ip(request))
    response["user"] = accounts_service.get_user(user_id)
    return response


@router.get("/audit")
def audit_log(limit: int = 200, offset: int = 0, user: SessionInfo = Depends(admin_only)) -> dict:
    return {"chain": audit.verify_chain(), "entries": audit.list_entries(min(limit, 1000), offset)}


@router.get("/stats")
def stats(user: SessionInfo = Depends(admin_only)) -> dict:
    users = accounts_service.list_users()
    by_role: dict[str, int] = {}
    for u in users:
        by_role[u["role"]] = by_role.get(u["role"], 0) + 1
    return {
        "users_by_role": by_role,
        "patients": len(accounts_service.list_patients()),
        "analyses_by_result": storage_service.class_counts(),
        "model_loaded": registry.loaded,
        "model_card": model_card().model_dump() if model_card() else None,
    }
