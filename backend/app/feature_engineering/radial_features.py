"""Radial intensity profile features I(r) (spec section 8 — Radial Features).

These are the features most directly tied to the physical spreading behaviour the
project cares about: how sharply intensity transitions from center -> ring -> background,
and how uniform that transition is around the full circle (radial_uniformity).
"""
from __future__ import annotations

import numpy as np

from app.image_processing.halo_detection import RadialProfile


def extract_radial_features(profile: RadialProfile) -> dict[str, float]:
    intensity = profile.mean_intensity
    if intensity.size < 5:
        return {
            "radial_peak_position": 0.0, "radial_slope_mean": 0.0, "radial_slope_max": 0.0,
            "radial_uniformity": 0.0, "radial_intensity_range": 0.0,
            "radial_n_transitions": 0.0,
        }

    gradient = np.gradient(intensity)
    peak_position = float(np.argmax(np.abs(gradient)))
    slope_mean = float(np.mean(np.abs(gradient)))
    slope_max = float(np.max(np.abs(gradient)))
    intensity_range = float(intensity.max() - intensity.min())

    # Radial uniformity: inverse of the angular-std / mean ratio, averaged over radius
    # (low angular std at a given radius = the ring is uniform around the circle).
    with np.errstate(divide="ignore", invalid="ignore"):
        rel_std = np.where(intensity > 1e-6, profile.std_intensity / (intensity + 1e-6), 0.0)
    radial_uniformity = float(np.clip(1.0 - np.mean(rel_std), 0.0, 1.0))

    # Count meaningful transitions (local extrema in gradient magnitude above noise floor).
    threshold = slope_mean + slope_max * 0.1
    n_transitions = int(np.sum(np.abs(gradient) > threshold))

    return {
        "radial_peak_position": peak_position,
        "radial_slope_mean": slope_mean,
        "radial_slope_max": slope_max,
        "radial_uniformity": radial_uniformity,
        "radial_intensity_range": intensity_range,
        "radial_n_transitions": float(n_transitions),
    }
