"""Fluid Spreading Profile (spec section 9).

Measurements are normalized by the detected sample-pad ROI radius rather than raw pixel
counts, so results are comparable across different camera distances/zoom levels without
requiring a physical reference marker (which the hardware-deferred MVP doesn't have yet —
see docs/architecture.md for the future reference-marker upgrade path).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.image_processing.halo_detection import HaloDetectionResult
from app.image_processing.roi_detection import ROI


@dataclass
class SpreadingProfile:
    spread_radius_normalized: float
    spread_area_normalized: float
    central_stain_area_normalized: float
    outer_diffusion_area_normalized: float
    diffusion_index: float
    directional_variance: float


def compute_spreading_profile(halo: HaloDetectionResult, roi: ROI) -> SpreadingProfile:
    pad_radius = max(roi.radius, 1.0)
    pad_area = np.pi * pad_radius**2

    spread_radius_normalized = float(halo.outer_radius / pad_radius)
    central_area = float(np.pi * halo.inner_radius**2)
    outer_area = float(np.pi * (halo.outer_radius**2 - halo.inner_radius**2)) if halo.outer_radius > halo.inner_radius else 0.0
    spread_area_normalized = float((central_area + outer_area) / pad_area)
    central_stain_area_normalized = float(central_area / pad_area)
    outer_diffusion_area_normalized = float(outer_area / pad_area)

    # Diffusion index: how far intensity decays outward relative to pad size, weighted by
    # how uniform that decay is around the circle (a clean radial gradient = organized
    # diffusion; noisy/asymmetric decay lowers the index).
    profile = halo.radial_profile
    if profile is not None and profile.mean_intensity.size > 2:
        intensity_range = float(profile.mean_intensity.max() - profile.mean_intensity.min()) + 1e-6
        mean_angular_std = float(profile.std_intensity.mean())
        decay_uniformity = float(np.clip(1.0 - mean_angular_std / intensity_range, 0.0, 1.0))
        directional_variance = float(np.clip(mean_angular_std / intensity_range, 0.0, 1.0))
    else:
        decay_uniformity = 0.0
        directional_variance = 0.0

    diffusion_index = float(np.clip(spread_radius_normalized * decay_uniformity, 0.0, 3.0))

    return SpreadingProfile(
        spread_radius_normalized=round(spread_radius_normalized, 4),
        spread_area_normalized=round(spread_area_normalized, 4),
        central_stain_area_normalized=round(central_stain_area_normalized, 4),
        outer_diffusion_area_normalized=round(outer_diffusion_area_normalized, 4),
        diffusion_index=round(diffusion_index, 4),
        directional_variance=round(directional_variance, 4),
    )


def extract_spreading_features(profile: SpreadingProfile) -> dict[str, float]:
    return {
        "spread_radius_normalized": profile.spread_radius_normalized,
        "spread_area_normalized": profile.spread_area_normalized,
        "spread_diffusion_index": profile.diffusion_index,
        "spread_directional_variance": profile.directional_variance,
    }
