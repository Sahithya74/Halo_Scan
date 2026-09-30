"""Granular pipeline-stage endpoints (spec section 21: /detect-halo, /extract-features,
/classify) — each reruns the pipeline up to that stage. /analyze remains the primary,
efficient end-to-end endpoint; these exist for debugging/research-mode inspection.
"""
from __future__ import annotations

import numpy as np

from app.feature_engineering.feature_vector import build_feature_vector, feature_dict_to_row
from app.image_processing.halo_detection import detect_halo
from app.image_processing.quality import assess_quality
from app.image_processing.roi_detection import detect_sample_region
from app.models.registry import registry
from app.services.analysis_service import build_decision_support, load_image_from_bytes
from app.spreading_analysis.spreading import compute_spreading_profile


def detect_halo_only(image_bytes: bytes) -> dict:
    image_bgr = load_image_from_bytes(image_bytes)
    roi = detect_sample_region(image_bgr)
    halo = detect_halo(image_bgr, roi)
    return {
        "roi": {"center_x": roi.center_x, "center_y": roi.center_y, "radius": roi.radius,
                "method": roi.method, "confidence": roi.confidence},
        "halo": {
            "detected": halo.detected, "center_x": halo.center_x, "center_y": halo.center_y,
            "inner_radius": halo.inner_radius, "outer_radius": halo.outer_radius,
            "halo_width": halo.halo_width, "circularity": halo.circularity,
            "symmetry_score": halo.symmetry_score, "confidence": halo.confidence,
            "messages": halo.messages,
        },
    }


def extract_features_only(image_bytes: bytes) -> dict:
    image_bgr = load_image_from_bytes(image_bytes)
    quality = assess_quality(image_bgr)
    if quality.status == "POOR":
        return {"status": "POOR_QUALITY", "reasons": quality.reasons, "features": {}}
    roi = detect_sample_region(image_bgr)
    halo = detect_halo(image_bgr, roi)
    if not halo.detected:
        return {"status": "NO_HALO_DETECTED", "features": {}}
    spreading = compute_spreading_profile(halo, roi)
    features = build_feature_vector(image_bgr, roi, halo, spreading)
    return {"status": "OK", "features": features}


def classify_only(image_bytes: bytes) -> dict:
    image_bgr = load_image_from_bytes(image_bytes)
    quality = assess_quality(image_bgr)
    if quality.status == "POOR":
        return {"status": "POOR_QUALITY", "decision_support": build_decision_support("RECAPTURE_NEEDED", None, None).model_dump()}
    roi = detect_sample_region(image_bgr)
    halo = detect_halo(image_bgr, roi)
    if not halo.detected:
        return {"status": "NO_HALO_DETECTED", "decision_support": build_decision_support("NO_HALO_DETECTED", None, None).model_dump()}
    if not registry.loaded:
        return {"status": "MODEL_NOT_LOADED", "detail": "Run scripts/train.py first."}

    spreading = compute_spreading_profile(halo, roi)
    features = build_feature_vector(image_bgr, roi, halo, spreading)
    x_row = np.array(feature_dict_to_row(features), dtype=np.float64)
    outcome = registry.predict(x_row)

    return {
        "status": "OK",
        "research_classification": outcome.ensemble.predicted_label,
        "confidence": outcome.ensemble.confidence,
        "class_probabilities": outcome.ensemble.class_probabilities,
        "uncertain": outcome.uncertainty.is_uncertain,
        "decision_support": build_decision_support(
            "OK", outcome.ensemble.predicted_label, outcome.uncertainty.is_uncertain
        ).model_dump(),
    }
