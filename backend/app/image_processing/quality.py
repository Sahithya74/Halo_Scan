"""Image quality assessment: blur, brightness, contrast, exposure -> GOOD/ACCEPTABLE/POOR.

Runs BEFORE any halo detection or classification. A POOR result short-circuits the
pipeline (see services/analysis_service.py) and asks the user to recapture, per spec
section 5 — we never classify a sample from a low-quality photo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from app.config import settings
from app.image_processing.preprocessing import to_grayscale


@dataclass
class QualityAssessment:
    status: str  # "GOOD" | "ACCEPTABLE" | "POOR"
    score: float  # 0..1
    sharpness_laplacian_var: float
    brightness_mean: float
    contrast_std: float
    overexposed_fraction: float
    underexposed_fraction: float
    resolution_ok: bool
    reasons: list[str] = field(default_factory=list)


def _sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness(gray: np.ndarray) -> float:
    return float(gray.mean())


def _contrast(gray: np.ndarray) -> float:
    return float(gray.std())


def _exposure_fractions(gray: np.ndarray) -> tuple[float, float]:
    # Thresholds are near true clipping (0/255), not just "bright" — a light-colored
    # sample pad legitimately fills much of the frame with high-but-detailed pixel values
    # (e.g. ~240-250), which is not the same failure mode as blown-out glare (~253+).
    total = gray.size
    under = float(np.count_nonzero(gray < 8)) / total
    over = float(np.count_nonzero(gray > 252)) / total
    return under, over


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def assess_quality(image_bgr: np.ndarray) -> QualityAssessment:
    gray = to_grayscale(image_bgr)
    h, w = gray.shape[:2]
    reasons: list[str] = []

    sharpness = _sharpness(gray)
    brightness = _brightness(gray)
    contrast = _contrast(gray)
    under_frac, over_frac = _exposure_fractions(gray)
    resolution_ok = min(h, w) >= settings.min_image_dimension

    if sharpness < settings.blur_laplacian_var_min_acceptable:
        reasons.append("Image appears blurry — hold the camera steady and focus on the sample.")
    if not (settings.brightness_min <= brightness <= settings.brightness_max):
        reasons.append("Lighting is too dark or too bright — use even, diffuse lighting.")
    if contrast < settings.contrast_std_min:
        reasons.append("Low contrast — the sample pad and background are hard to distinguish.")
    if over_frac > settings.overexposed_pixel_fraction_max:
        reasons.append("Image is overexposed (glare/reflection) — reduce direct light on the pad.")
    if under_frac > settings.underexposed_pixel_fraction_max:
        reasons.append("Image is underexposed — increase lighting.")
    if not resolution_ok:
        reasons.append(f"Resolution too low — minimum {settings.min_image_dimension}px on the short side.")

    # Component scores, each 0..1, then weighted combination (spec section 5).
    sharpness_score = _clamp01(sharpness / settings.blur_laplacian_var_min_good)
    brightness_mid = (settings.brightness_min + settings.brightness_max) / 2
    brightness_half_range = (settings.brightness_max - settings.brightness_min) / 2
    brightness_score = _clamp01(1.0 - abs(brightness - brightness_mid) / brightness_half_range)
    contrast_score = _clamp01(contrast / (settings.contrast_std_min * 2))
    exposure_score = _clamp01(1.0 - (over_frac + under_frac) * 2)
    resolution_score = 1.0 if resolution_ok else 0.0

    score = (
        0.35 * sharpness_score
        + 0.20 * brightness_score
        + 0.15 * contrast_score
        + 0.20 * exposure_score
        + 0.10 * resolution_score
    )
    score = _clamp01(score)

    if score >= settings.quality_score_good_min and resolution_ok:
        status = "GOOD"
    elif score >= settings.quality_score_acceptable_min and resolution_ok:
        status = "ACCEPTABLE"
    else:
        status = "POOR"

    return QualityAssessment(
        status=status,
        score=round(score, 4),
        sharpness_laplacian_var=round(sharpness, 2),
        brightness_mean=round(brightness, 2),
        contrast_std=round(contrast, 2),
        overexposed_fraction=round(over_frac, 4),
        underexposed_fraction=round(under_frac, 4),
        resolution_ok=resolution_ok,
        reasons=reasons,
    )
