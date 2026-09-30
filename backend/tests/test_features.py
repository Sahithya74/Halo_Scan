import numpy as np

from app.feature_engineering.feature_vector import FEATURE_COLUMNS, build_feature_vector, feature_dict_to_row
from app.image_processing.halo_detection import detect_halo
from app.image_processing.roi_detection import detect_sample_region
from app.spreading_analysis.spreading import compute_spreading_profile


def test_feature_vector_is_deterministic(ring_image_factory):
    image = ring_image_factory(size=400, center=(200, 200), inner_r=60, outer_r=130)
    roi = detect_sample_region(image)
    halo = detect_halo(image, roi)
    spreading = compute_spreading_profile(halo, roi)

    features_a = build_feature_vector(image, roi, halo, spreading)
    features_b = build_feature_vector(image, roi, halo, spreading)
    assert features_a == features_b


def test_feature_row_matches_column_order(ring_image_factory):
    image = ring_image_factory()
    roi = detect_sample_region(image)
    halo = detect_halo(image, roi)
    spreading = compute_spreading_profile(halo, roi)
    features = build_feature_vector(image, roi, halo, spreading)

    row = feature_dict_to_row(features)
    assert len(row) == len(FEATURE_COLUMNS)
    assert all(isinstance(v, float) for v in row)
    assert not any(np.isnan(row))


def test_no_missing_required_columns(ring_image_factory):
    image = ring_image_factory()
    roi = detect_sample_region(image)
    halo = detect_halo(image, roi)
    spreading = compute_spreading_profile(halo, roi)
    features = build_feature_vector(image, roi, halo, spreading)

    missing = [c for c in FEATURE_COLUMNS if c not in features]
    assert missing == []
