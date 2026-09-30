"""Primary analysis endpoints (spec section 21)."""
from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.config import settings
from app.models.registry import registry
from app.schemas.analysis import AnalysisResult, HealthResponse, HistoryItem, ModelInfoResponse
from app.services import storage_service
from app.services.analysis_service import run_full_analysis
from app.services.granular_endpoints import classify_only, detect_halo_only, extract_features_only
from app.services.image_quality_only import quality_check_only

router = APIRouter(prefix="/api", tags=["analysis"])

_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
_ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _read_validated_image(file: UploadFile) -> bytes:
    if file.content_type not in _ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported content type: {file.content_type}")
    data = await file.read()
    if len(data) == 0:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File too large (max 15MB).")
    return data


@router.post("/analyze", response_model=AnalysisResult)
async def analyze(file: UploadFile = File(...)) -> AnalysisResult:
    data = await _read_validated_image(file)
    try:
        return run_full_analysis(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/quality-check")
async def quality_check(file: UploadFile = File(...)) -> dict:
    data = await _read_validated_image(file)
    try:
        return quality_check_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/detect-halo")
async def detect_halo_endpoint(file: UploadFile = File(...)) -> dict:
    data = await _read_validated_image(file)
    try:
        return detect_halo_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/extract-features")
async def extract_features_endpoint(file: UploadFile = File(...)) -> dict:
    data = await _read_validated_image(file)
    try:
        return extract_features_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/classify")
async def classify_endpoint(file: UploadFile = File(...)) -> dict:
    data = await _read_validated_image(file)
    try:
        return classify_only(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str) -> dict:
    result = storage_service.get_analysis(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found.")
    return result


@router.get("/history", response_model=list[HistoryItem])
async def history(limit: int = 50) -> list[HistoryItem]:
    return [HistoryItem(**row) for row in storage_service.list_history(limit)]


@router.get("/model-info", response_model=ModelInfoResponse)
async def model_info() -> ModelInfoResponse:
    if not registry.loaded:
        raise HTTPException(status_code=503, detail="Model not loaded. Run scripts/train.py first.")
    return ModelInfoResponse(
        model_version=settings.model_version,
        classes=registry.classes,
        trained_on=registry.metadata.get("trained_on", "unknown"),
        metrics=registry.metadata.get("metrics", {}),
    )


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", model_version=settings.model_version, model_loaded=registry.loaded)
