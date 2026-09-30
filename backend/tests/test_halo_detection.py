from app.image_processing.halo_detection import detect_halo
from app.image_processing.roi_detection import detect_sample_region


def test_detects_clear_ring(ring_image_factory):
    image = ring_image_factory(size=400, center=(200, 200), inner_r=60, outer_r=130)
    roi = detect_sample_region(image)
    halo = detect_halo(image, roi)
    assert halo.detected is True
    assert halo.inner_radius < halo.outer_radius
    # Rendered ring: inner=60, outer=130 -> detected radii should be roughly in that ballpark.
    assert 30 < halo.inner_radius < 100
    assert 90 < halo.outer_radius < 170
    assert halo.halo_width > 0


def test_no_ring_when_image_is_flat_background():
    import numpy as np
    flat = np.full((400, 400, 3), 240, dtype="uint8")
    roi = detect_sample_region(flat)
    halo = detect_halo(flat, roi)
    assert halo.detected is False


def test_radial_profile_populated(ring_image_factory):
    image = ring_image_factory()
    roi = detect_sample_region(image)
    halo = detect_halo(image, roi)
    assert halo.radial_profile is not None
    assert halo.radial_profile.mean_intensity.size > 10
