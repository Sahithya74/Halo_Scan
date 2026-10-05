"""Compares a sample's key measurements with each class's reference profile.

Profiles (per-class mean/std of a few interpretable features) are computed from the training
set and saved in trained_models/metadata.json, so the comparison always reflects the model
actually loaded.
"""
from __future__ import annotations

import numpy as np

from app.feature_engineering.feature_vector import FEATURE_COLUMNS

PROFILE_FEATURES = [
    "geo_ring_width_ratio",
    "spread_radius_normalized",
    "spread_diffusion_index",
    "color_ring_saturation_mean",
    "tex_glcm_entropy",
    "geo_circularity",
]
FEATURE_LABELS = {
    "geo_ring_width_ratio": "Ring width ratio",
    "spread_radius_normalized": "Spread radius",
    "spread_diffusion_index": "Diffusion index",
    "color_ring_saturation_mean": "Ring saturation",
    "tex_glcm_entropy": "Texture entropy",
    "geo_circularity": "Circularity",
}


def compute_class_profiles(X: np.ndarray, y_idx: np.ndarray, classes: list[str]) -> dict:
    cols = [FEATURE_COLUMNS.index(f) for f in PROFILE_FEATURES]
    profiles = {}
    for i, cls in enumerate(classes):
        Xc = X[y_idx == i][:, cols]
        if Xc.shape[0] == 0:
            continue
        profiles[cls] = {
            f: {"mean": float(Xc[:, j].mean()), "std": float(Xc[:, j].std() or 1e-6)}
            for j, f in enumerate(PROFILE_FEATURES)
        }
    return profiles


def compare(features: dict[str, float], class_profiles: dict) -> dict | None:
    if not class_profiles:
        return None
    sample = {f: float(features.get(f, 0.0)) for f in PROFILE_FEATURES}
    similarity = {}
    for cls, profile in class_profiles.items():
        z = np.array([(sample[f] - profile[f]["mean"]) / max(profile[f]["std"], 1e-6) for f in PROFILE_FEATURES])
        rms = float(np.sqrt(np.mean(z ** 2)))
        similarity[cls] = round(100.0 * float(np.exp(-0.5 * rms ** 2 / 4.0)), 1)
    return {
        "features": PROFILE_FEATURES,
        "feature_labels": FEATURE_LABELS,
        "sample_values": {k: round(v, 4) for k, v in sample.items()},
        "class_similarity": similarity,
        "closest_class": max(similarity, key=similarity.get),
    }
