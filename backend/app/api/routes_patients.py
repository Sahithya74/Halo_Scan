"""Patient registration and records (doctor/nurse), and a patient's own results."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.security import audit
from app.security.rbac import STAFF_ROLES, client_ip, require_roles
from app.security.sessions import SessionInfo
from app.services import accounts_service, storage_service

router = APIRouter(prefix="/api", tags=["patients"])
staff_only = require_roles(*STAFF_ROLES)
patient_only = require_roles("patient")


class RegisterPatientRequest(BaseModel):
    mrn: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    dob: str | None = Field(default=None, max_length=10)  # YYYY-MM-DD
    sex: str | None = Field(default=None, max_length=1)
    create_login: bool = True


@router.get("/patients")
def list_patients(request: Request, q: str | None = None, user: SessionInfo = Depends(staff_only)) -> list[dict]:
    patients = accounts_service.list_patients(q)
    audit.record("patient_list", user_id=user.user_id, username=user.username, role=user.role,
                 ip=client_ip(request), detail=f"results={len(patients)}")
    return patients


@router.post("/patients")
def register_patient(body: RegisterPatientRequest, request: Request, user: SessionInfo = Depends(staff_only)) -> dict:
    try:
        result = accounts_service.register_patient(body.mrn, body.name, body.dob, body.sex,
                                                   created_by=user.user_id, create_login=body.create_login)
    except accounts_service.AccountError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit.record("patient_register", user_id=user.user_id, username=user.username, role=user.role,
                 target=f"patient:{result['patient']['id']}", ip=client_ip(request))
    return result


@router.get("/patients/{patient_id}")
def get_patient(patient_id: int, request: Request, user: SessionInfo = Depends(staff_only)) -> dict:
    patient = accounts_service.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    audit.record("patient_view", user_id=user.user_id, username=user.username, role=user.role,
                 target=f"patient:{patient_id}", ip=client_ip(request))
    return patient


@router.get("/patients/{patient_id}/analyses")
def patient_analyses(patient_id: int, user: SessionInfo = Depends(staff_only)) -> list[dict]:
    if accounts_service.get_patient(patient_id) is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return storage_service.list_history(limit=100, patient_id=patient_id)


@router.get("/me/analyses")
def my_analyses(user: SessionInfo = Depends(patient_only)) -> list[dict]:
    if user.patient_id is None:
        return []
    return storage_service.list_history(limit=100, patient_id=user.patient_id)


@router.get("/me/patient")
def my_patient_record(user: SessionInfo = Depends(patient_only)) -> dict:
    patient = accounts_service.get_patient(user.patient_id) if user.patient_id else None
    if patient is None:
        raise HTTPException(status_code=404, detail="No patient record is linked to this account.")
    return {"patient_code": patient["patient_code"], "name": patient["name"]}
