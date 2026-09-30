"""Geometric features derived from the detected halo (spec section 8 — Geometry)."""
from __future__ import annotations

import numpy as np

from app.image_processing.halo_detection import HaloDetectionResult
from app.image_processing.roi_detection import ROI


def extract_geometry_features(halo: HaloDetectionResult, roi: ROI) -> dict[str, float]:
    inner = halo.inner_radius
    outer = halo.outer_radius
    width = halo.halo_width
    diameter = outer * 2
    area = float(np.pi * (outer**2 - inner**2)) if outer > inner else 0.0
    circumference = float(2 * np.pi * outer)
    width_ratio = float(width / outer) if outer > 0 else 0.0
    center_displacement = float(np.hypot(halo.center_x - roi.center_x, halo.center_y - roi.center_y))
    eccentricity_proxy = float(1.0 - halo.circularity)  # 0 = perfectly circular

    return {
        "geo_inner_radius": inner,
        "geo_outer_radius": outer,
        "geo_ring_width": width,
        "geo_ring_width_ratio": width_ratio,
        "geo_diameter": diameter,
        "geo_area": area,
        "geo_circumference": circumference,
        "geo_circularity": halo.circularity,
        "geo_eccentricity_proxy": eccentricity_proxy,
        "geo_symmetry": halo.symmetry_score,
        "geo_center_displacement": center_displacement,
    }
