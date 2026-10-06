"""Analysis endpoints. Doctors/nurses run analyses; patients can only read their own."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.image_processing.sample_validation import NotASampleError
from app.models.registry import registry
from app.schemas.analysis import AnalysisResult, HealthResponse, HistoryItem, ModelInfoResponse
from app.security import audit
from app.security.rbac import STAFF_ROLES, client_ip, current_user, require_roles
from app.security.sessions import SessionInfo
from app.services import accounts_service, storage_service
from app.services.analysis_service import run_full_analysis
from app.services.granular_endpoints import classify_only, detect_halo_only, extract_features_only
from app.services.image_quality_only import quality_check_only
from app.services.video_service import VideoError, run_video_analysis

router = APIRouter(prefix="/api", tags=["analysis"])
staff_only = require_roles(*STAFF_ROLES)
logger = logging.getLogger(__name__)

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}


def _base_type(content_type: str | None) -> str:
    # Browsers send e.g. "video/webm;codecs=vp9" for MediaRecorder output.
    return (content_type or "").split(";")[0].strip().lower()


async def _read_upload(file: UploadFile, allowed: set[str]) -> tuple[bytes, str]:
    ctype = _base_type(file.content_type)
    if ctype not in allowed:
        raise HTTPException(status_code=415, detail=(
            f"Unsupported file type ({file.content_type or 'unknown'}). Use a JPEG/PNG/WebP photo or an "
            "MP4/WebM/MOV video. iPhone HEIC photos: set Camera > Formats > Most Compatible, or use the in-app camera."))
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail=f"File too large (max {settings.max_upload_bytes // (1024 * 1024)}MB).")
    return data, ctype


async def _read_validated_image(file: UploadFile) -> bytes:
    data, _ = await _read_upload(file, _IMAGE_TYPES)
    return data


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(
    request: Request, file: UploadFile = File(...), patient_id: int = Form(...),
    user: SessionInfo = Depends(staff_only),
) -> AnalysisResult:
    patient = accounts_service.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    data, ctype = await _read_upload(file, _IMAGE_TYPES | _VIDEO_TYPES)
    kwargs = dict(patient_id=patient_id, patient_code=patient["patient_code"], performed_by=user.user_id)
    try:
        if ctype in _VIDEO_TYPES:
            result = await run_in_threadpool(run_video_analysis, data, ctype, **kwargs)
        else:
            result = await run_in_threadpool(run_full_analysis, data, **kwargs)
    except NotASampleError as e:
        # Nothing about the image is stored — only that a rejection happened and why. The
        # numeric check values are logged so the gate can be recalibrated on real photos.
        logger.info("Sample rejected (%s): %s", e.reason, e.metrics)
        audit.record("analysis_rejected", user_id=user.user_id, username=user.username, role=user.role,
                     ip=client_ip(request), success=False, detail=f"patient:{patient_id} reason:{e.reason}")
        raise HTTPException(status_code=422, detail={"code": "not_a_sample", "reason": e.reason, "message": str(e)})
    except (ValueError, VideoError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit.record("analysis_run", user_id=user.user_id, username=user.username, role=user.role,
                 target=f"analysis:{result.analysis_id}", ip=client_ip(request),
                 detail=f"patient:{patient_id} input:{result.input_type} status:{result.status}")
    return result


@router.post("/quality-check")
async def quality_check(file: UploadFile = File(...), user: SessionInfo = Depends(staff_only)) -> dict:
    data = await _read_validated_image(file)
    try:
        return quality_check_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/detect-halo")
async def detect_halo_endpoint(file: UploadFile = File(...), user: SessionInfo = Depends(staff_only)) -> dict:
    data = await _read_validated_image(file)
    try:
        return detect_halo_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/extract-features")
async def extract_features_endpoint(file: UploadFile = File(...), user: SessionInfo = Depends(staff_only)) -> dict:
    data = await _read_validated_image(file)
    try:
        return extract_features_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/classify")
async def classify_endpoint(file: UploadFile = File(...), user: SessionInfo = Depends(staff_only)) -> dict:
    data = await _read_validated_image(file)
    try:
        return classify_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analysis/{analysis_id}")
def get_analysis(analysis_id: str, request: Request, user: SessionInfo = Depends(current_user)) -> dict:
    record = storage_service.get_analysis(analysis_id)
    # Patients get the same 404 for "doesn't exist" and "not yours", so ids can't be probed.
    if record is None or (user.role == "patient" and record["patient_id"] != user.patient_id):
        raise HTTPException(status_code=404, detail="Analysis not found.")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="Administrators manage the system, not patient results.")
    audit.record("analysis_view", user_id=user.user_id, username=user.username, role=user.role,
                 target=f"analysis:{analysis_id}", ip=client_ip(request))
    return record["result"]


@router.get("/history", response_model=list[HistoryItem])
def history(limit: int = 50, patient_id: int | None = None, user: SessionInfo = Depends(current_user)) -> list[HistoryItem]:
    if user.role == "patient":
        patient_id = user.patient_id
        if patient_id is None:
            return []
    elif user.role not in STAFF_ROLES:
        raise HTTPException(status_code=403, detail="Your role cannot access this resource.")
    return [HistoryItem(**row) for row in storage_service.list_history(min(limit, 200), patient_id)]


@router.get("/model-info", response_model=ModelInfoResponse)
def model_info(user: SessionInfo = Depends(current_user)) -> ModelInfoResponse:
    if not registry.loaded:
        raise HTTPException(status_code=503, detail="Model not loaded. Run scripts/train.py first.")
    return ModelInfoResponse(
        model_version=settings.model_version,
        classes=registry.classes,
        trained_on=registry.metadata.get("trained_on", "unknown"),
        metrics=registry.metadata.get("metrics", {}),
    )


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", model_version=settings.model_version, model_loaded=registry.loaded)
