"""Assembles the full structured feature vector — the single source of truth for
column order, used identically by training (models/classical_ml.py) and inference
(services/analysis_service.py) so the two can never drift apart.
"""
from __future__ import annotations

import numpy as np

from app.feature_engineering._masks import build_region_masks
from app.feature_engineering.color_features import extract_color_features
from app.feature_engineering.geometry_features import extract_geometry_features
from app.feature_engineering.intensity_features import extract_intensity_features
from app.feature_engineering.radial_features import extract_radial_features
from app.feature_engineering.texture_features import extract_texture_features
from app.image_processing.halo_detection import HaloDetectionResult
from app.image_processing.roi_detection import ROI
from app.spreading_analysis.spreading import SpreadingProfile, extract_spreading_features


def build_feature_vector(
    image_bgr: np.ndarray,
    roi: ROI,
    halo: HaloDetectionResult,
    spreading: SpreadingProfile,
) -> dict[str, float]:
    masks = build_region_masks(image_bgr.shape, halo)

    features: dict[str, float] = {}
    features.update(extract_geometry_features(halo, roi))
    features.update(extract_intensity_features(image_bgr, masks))
    features.update(extract_radial_features(halo.radial_profile))
    features.update(extract_color_features(image_bgr, masks))
    features.update(extract_texture_features(image_bgr, masks))
    features.update(extract_spreading_features(spreading))
    return features


# Fixed, explicit column order for ML input — never rely on dict insertion order alone
# across module versions.
FEATURE_COLUMNS: list[str] = [
    "geo_inner_radius", "geo_outer_radius", "geo_ring_width", "geo_ring_width_ratio",
    "geo_diameter", "geo_area", "geo_circumference", "geo_circularity",
    "geo_eccentricity_proxy", "geo_symmetry", "geo_center_displacement",
    "int_mean", "int_median", "int_min", "int_max", "int_std",
    "int_central_mean", "int_central_std", "int_ring_mean", "int_ring_std",
    "int_background_mean", "int_center_to_background_gradient", "int_ring_to_center_contrast",
    "radial_peak_position", "radial_slope_mean", "radial_slope_max", "radial_uniformity",
    "radial_intensity_range", "radial_n_transitions",
    "color_center_r_mean", "color_center_r_std", "color_center_g_mean", "color_center_g_std",
    "color_center_b_mean", "color_center_b_std", "color_center_hue_mean", "color_center_hue_std",
    "color_center_saturation_mean", "color_center_saturation_std",
    "color_center_value_mean", "color_center_value_std",
    "color_center_lab_a_mean", "color_center_lab_a_std", "color_center_lab_b_mean", "color_center_lab_b_std",
    "color_ring_r_mean", "color_ring_r_std", "color_ring_g_mean", "color_ring_g_std",
    "color_ring_b_mean", "color_ring_b_std", "color_ring_hue_mean", "color_ring_hue_std",
    "color_ring_saturation_mean", "color_ring_saturation_std",
    "color_ring_value_mean", "color_ring_value_std",
    "color_ring_lab_a_mean", "color_ring_lab_a_std", "color_ring_lab_b_mean", "color_ring_lab_b_std",
    "color_saturation_gradient",
    "tex_glcm_contrast", "tex_glcm_homogeneity", "tex_glcm_energy", "tex_glcm_correlation",
    "tex_glcm_entropy", "tex_lbp_entropy",
    "spread_radius_normalized", "spread_area_normalized", "spread_diffusion_index",
    "spread_directional_variance",
]


def feature_dict_to_row(features: dict[str, float]) -> list[float]:
    return [float(features.get(col, 0.0)) for col in FEATURE_COLUMNS]
