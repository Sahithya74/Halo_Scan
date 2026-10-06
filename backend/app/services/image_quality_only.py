"""Standalone /api/quality-check — lets the Flutter capture screen validate a frame
before committing to the full analyze pipeline (spec section 3, pre-capture checks)."""
from __future__ import annotations

from app.image_processing.quality import assess_quality
from app.image_processing.sample_validation import validate_sample
from app.services.analysis_service import load_image_from_bytes


def quality_check_only(image_bytes: bytes) -> dict:
    image_bgr = load_image_from_bytes(image_bytes)
    quality = assess_quality(image_bgr)
    sample = validate_sample(image_bgr)
    return {
        "sample_check": {"ok": sample.ok, "reason": sample.reason, "message": sample.message},
        "status": quality.status,
        "score": quality.score,
        "sharpness_laplacian_var": quality.sharpness_laplacian_var,
        "brightness_mean": quality.brightness_mean,
        "contrast_std": quality.contrast_std,
        "overexposed_fraction": quality.overexposed_fraction,
        "underexposed_fraction": quality.underexposed_fraction,
        "resolution_ok": quality.resolution_ok,
        "reasons": quality.reasons,
    }
