"""Grayscale intensity features per region (spec section 8 — Intensity)."""
from __future__ import annotations

import numpy as np

from app.feature_engineering._masks import RegionMasks
from app.image_processing.preprocessing import to_grayscale


def _stats(values: np.ndarray) -> tuple[float, float, float, float, float]:
    if values.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    return (
        float(values.mean()), float(np.median(values)), float(values.min()),
        float(values.max()), float(values.std()),
    )


def extract_intensity_features(image_bgr: np.ndarray, masks: RegionMasks) -> dict[str, float]:
    gray = to_grayscale(image_bgr).astype(np.float64)

    center_vals = gray[masks.center == 1]
    ring_vals = gray[masks.ring == 1]
    bg_vals = gray[masks.background == 1]

    c_mean, c_med, c_min, c_max, c_std = _stats(center_vals)
    r_mean, r_med, r_min, r_max, r_std = _stats(ring_vals)
    b_mean, _, _, _, _ = _stats(bg_vals)

    all_vals = gray[(masks.center | masks.ring | masks.background) == 1]
    a_mean, a_med, a_min, a_max, a_std = _stats(all_vals)

    gradient = float(b_mean - c_mean)  # background (bright pad) minus central stain

    return {
        "int_mean": a_mean, "int_median": a_med, "int_min": a_min, "int_max": a_max, "int_std": a_std,
        "int_central_mean": c_mean, "int_central_std": c_std,
        "int_ring_mean": r_mean, "int_ring_std": r_std,
        "int_background_mean": b_mean,
        "int_center_to_background_gradient": gradient,
        "int_ring_to_center_contrast": float(r_mean - c_mean),
    }
