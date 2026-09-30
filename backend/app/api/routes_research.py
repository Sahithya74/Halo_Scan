"""Research/development-mode endpoints (spec section 20, Page 8). Not a clinical
interface — dataset generation, training and evaluation for the synthetic pipeline."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.registry import registry

router = APIRouter(prefix="/api/research", tags=["research"])


@router.post("/upload-dataset")
async def upload_dataset(sessions_per_class: int = 40) -> dict:
    """No real labeled dataset exists yet (see docs/dataset.md) — this (re)generates the
    synthetic dataset. Swap this out once real, ethically-sourced labeled data exists."""
    from app.services.research_service import generate_synthetic_dataset
    return generate_synthetic_dataset(sessions_per_class=sessions_per_class)


@router.post("/train")
async def train() -> dict:
    from app.services.research_service import train_models
    try:
        metadata = train_models()
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    registry.load()
    return metadata


@router.post("/evaluate")
async def evaluate() -> dict:
    from app.services.research_service import evaluate_models
    try:
        return evaluate_models()
    except (FileNotFoundError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
