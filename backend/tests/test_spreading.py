import numpy as np

from app.image_processing.halo_detection import HaloDetectionResult, RadialProfile
from app.image_processing.roi_detection import ROI
from app.spreading_analysis.spreading import compute_spreading_profile, extract_spreading_features


def _make_halo(inner_radius, outer_radius, radii=None, mean_intensity=None, std_intensity=None):
    if radii is None:
        radii = np.arange(0, 200, dtype=np.float64)
        mean_intensity = np.linspace(50, 240, radii.size)
        std_intensity = np.full(radii.size, 2.0)
    return HaloDetectionResult(
        detected=True, center_x=100.0, center_y=100.0,
        inner_radius=inner_radius, outer_radius=outer_radius,
        halo_width=outer_radius - inner_radius, circularity=0.9, symmetry_score=0.9,
        confidence=0.8,
        radial_profile=RadialProfile(radii=radii, mean_intensity=mean_intensity, std_intensity=std_intensity),
    )


def test_spread_radius_normalized_matches_ratio():
    halo = _make_halo(inner_radius=40.0, outer_radius=80.0)
    roi = ROI(center_x=100.0, center_y=100.0, radius=100.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    assert profile.spread_radius_normalized == round(80.0 / 100.0, 4)


def test_area_components_sum_to_total():
    halo = _make_halo(inner_radius=30.0, outer_radius=90.0)
    roi = ROI(center_x=100.0, center_y=100.0, radius=120.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    assert abs(
        (profile.central_stain_area_normalized + profile.outer_diffusion_area_normalized)
        - profile.spread_area_normalized
    ) < 1e-6


def test_degenerate_outer_not_greater_than_inner_gives_zero_outer_area():
    halo = _make_halo(inner_radius=50.0, outer_radius=50.0)
    roi = ROI(center_x=100.0, center_y=100.0, radius=100.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    assert profile.outer_diffusion_area_normalized == 0.0


def test_diffusion_index_is_bounded():
    halo = _make_halo(inner_radius=10.0, outer_radius=300.0)
    roi = ROI(center_x=100.0, center_y=100.0, radius=50.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    assert 0.0 <= profile.diffusion_index <= 3.0


def test_uniform_radial_decay_gives_high_diffusion_index():
    # Smooth, low angular-std radial profile -> high decay_uniformity -> higher index
    # than a noisy one with the same spread radius.
    radii = np.arange(0, 200, dtype=np.float64)
    smooth_mean = np.linspace(50, 240, radii.size)
    smooth_std = np.full(radii.size, 1.0)
    noisy_std = np.full(radii.size, 60.0)

    roi = ROI(center_x=100.0, center_y=100.0, radius=100.0, method="hough", confidence=0.9)
    smooth_halo = _make_halo(40.0, 80.0, radii, smooth_mean, smooth_std)
    noisy_halo = _make_halo(40.0, 80.0, radii, smooth_mean, noisy_std)

    smooth_profile = compute_spreading_profile(smooth_halo, roi)
    noisy_profile = compute_spreading_profile(noisy_halo, roi)
    assert smooth_profile.diffusion_index > noisy_profile.diffusion_index


def test_extract_spreading_features_keys_and_values():
    halo = _make_halo(inner_radius=20.0, outer_radius=60.0)
    roi = ROI(center_x=100.0, center_y=100.0, radius=100.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    features = extract_spreading_features(profile)

    assert set(features.keys()) == {
        "spread_radius_normalized", "spread_area_normalized",
        "spread_diffusion_index", "spread_directional_variance",
    }
    assert features["spread_radius_normalized"] == profile.spread_radius_normalized
    assert features["spread_diffusion_index"] == profile.diffusion_index


def test_missing_radial_profile_defaults_to_zero_diffusion():
    halo = HaloDetectionResult(
        detected=True, center_x=0.0, center_y=0.0, inner_radius=10.0, outer_radius=20.0,
        halo_width=10.0, circularity=0.9, symmetry_score=0.9, confidence=0.8,
        radial_profile=None,
    )
    roi = ROI(center_x=0.0, center_y=0.0, radius=50.0, method="hough", confidence=0.9)
    profile = compute_spreading_profile(halo, roi)
    assert profile.diffusion_index == 0.0
    assert profile.directional_variance == 0.0
